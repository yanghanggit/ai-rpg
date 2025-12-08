from pathlib import Path
from typing import Final, List, Set, final
import json
import hashlib
from loguru import logger
from overrides import override
from ..chat_services.client import ChatClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.rpg_game import RPGGame
from ..models import (
    ActorComponent,
    EnvironmentComponent,
    KickOffDoneComponent,
    KickOffComponent,
    StageComponent,
    WorldComponent,
)
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from ..game.config import LOGS_DIR


###############################################################################################################################################
@final
class KickOffSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: RPGGame, enable_cache: bool) -> None:
        self._game: RPGGame = game_context
        self._enable_cache: Final[bool] = enable_cache

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:

        # 处理请求
        valid_entities = self._filter_valid_kick_off_entities()
        if len(valid_entities) == 0:
            return

        # cache pre-process，如果在logs目录下有缓存文件，则直接加载, 并从valid_entities中移除
        if self._enable_cache:
            entities_to_process = self._load_cached_responses(valid_entities)
        else:
            entities_to_process = valid_entities

        if len(entities_to_process) == 0:
            logger.warning(
                "KickOffSystem: All entities loaded from cache, no new requests needed"
            )
            return

        # 处理请求
        await self._execute_kick_off_requests(entities_to_process)

    ###############################################################################################################################################
    def _load_cached_responses(self, entities: Set[Entity]) -> Set[Entity]:
        """
        加载缓存的启动响应，并从待处理实体中移除已有缓存的实体

        Args:
            entities: 待处理的实体集合

        Returns:
            Set[Entity]: 需要实际处理的实体集合（移除了有缓存的实体）
        """
        entities_to_process = entities.copy()

        for entity in entities:
            # 获取系统消息和提示内容
            system_content = self._get_system_content(entity)
            kickoff_message_content = self._get_kick_off_message_content(entity)
            cache_path = self._get_kick_off_cache_path(
                entity.name, system_content, kickoff_message_content
            )

            if cache_path.exists():
                try:
                    # 加载缓存的AI消息
                    cached_data = json.loads(cache_path.read_text(encoding="utf-8"))

                    # 直接使用model_validate反序列化AI消息对象
                    ai_messages = [
                        AIMessage.model_validate(msg_data) for msg_data in cached_data
                    ]

                    # 使用现有函数整合聊天上下文（prompt已在上面获取）
                    self._prepend_kickoff_messages(
                        entity, kickoff_message_content, ai_messages
                    )

                    # 标记为已完成
                    entity.replace(
                        KickOffDoneComponent,
                        entity.name,
                        ai_messages[0].content if ai_messages else "",
                    )

                    # 若是场景，用response替换narrate
                    if entity.has(StageComponent):
                        entity.replace(
                            EnvironmentComponent,
                            entity.name,
                            ai_messages[0].content if ai_messages else "",
                        )

                    # 从待处理集合中移除
                    entities_to_process.discard(entity)

                    logger.debug(
                        f"KickOffSystem: Loaded cached response for {entity.name}"
                    )

                except Exception as e:
                    logger.warning(
                        f"KickOffSystem: Failed to load cache for {entity.name}: {e}, will process normally"
                    )
                    # 如果加载缓存失败，保留在待处理集合中

        return entities_to_process

    ###############################################################################################################################################
    def _prepend_kickoff_messages(
        self, entity: Entity, prompt: str, ai_messages: List[AIMessage]
    ) -> None:
        """
        整合聊天上下文，将请求处理结果添加到实体的聊天历史中

        Args:
            entity: 实体对象
            prompt: 人类消息提示内容
            ai_messages: AI消息列表

        处理两种情况：
        1. 如果聊天历史第一条是system message，则重新构建消息序列
        2. 否则使用常规方式添加消息
        """
        agent_context = self._game.get_agent_context(entity)
        assert len(agent_context.context) >= 1, "聊天上下文不能为空"
        assert agent_context.context[0].type == "system", "第一条必须是system message!"

        # 确保类型正确的消息列表
        message_context_list: List[SystemMessage | HumanMessage | AIMessage] = [
            agent_context.context[0]  # system message
        ]

        # 添加human message, 需要特殊标记：kickoff_message
        message_context_list.append(HumanMessage(content=prompt, kickoff=entity.name))
        message_context_list.extend(ai_messages)

        # 移除原有的system message
        agent_context.context.pop(0)

        # 将新的上下文消息添加到聊天历史的开头
        agent_context.context = message_context_list + agent_context.context

        # 打印调试信息
        logger.info(f"Integrate context for entity: {entity.name}")
        logger.debug(f"{prompt}")
        for ai_msg in ai_messages:
            logger.debug(f"{str(ai_msg.content)}")

    ###############################################################################################################################################
    def _cache_kick_off_response(
        self, entity: Entity, ai_messages: List[AIMessage]
    ) -> None:
        """
        缓存启动响应到文件系统

        Args:
            entity: 实体对象
            ai_messages: AI消息列表
        """
        try:
            # 获取系统消息和提示内容
            system_content = self._get_system_content(entity)
            kickoff_message_content = self._get_kick_off_message_content(entity)

            # 构建基于内容哈希的文件路径
            path = self._get_kick_off_cache_path(
                entity.name, system_content, kickoff_message_content
            )

            # 确保目录存在
            path.parent.mkdir(parents=True, exist_ok=True)

            # 直接序列化AIMessage（BaseModel）
            messages_data = [msg.model_dump() for msg in ai_messages]

            # 写入JSON文件
            path.write_text(
                json.dumps(messages_data, ensure_ascii=False),
                encoding="utf-8",
            )

            logger.debug(
                f"KickOffSystem: Cached kick off response for {entity.name} to {path.name}"
            )

        except Exception as e:
            logger.error(
                f"KickOffSystem: Failed to cache kick off response for {entity.name}: {e}"
            )

    ###############################################################################################################################################
    def _get_system_content(self, entity: Entity) -> str:
        """
        获取实体的系统消息内容

        Args:
            entity: 实体对象

        Returns:
            str: 系统消息内容，如果没有则返回空字符串
        """
        agent_context = self._game.get_agent_context(entity)
        if len(agent_context.context) > 0 and agent_context.context[0].type == "system":
            return str(agent_context.context[0].content)
        return ""

    ###############################################################################################################################################
    def _get_kick_off_cache_path(
        self, entity_name: str, system_content: str, prompt_content: str
    ) -> Path:
        """
        解析并返回基于内容哈希的kick off缓存文件路径

        Args:
            system_content: 系统消息内容
            prompt_content: 提示内容

        Returns:
            Path: 基于内容哈希的缓存文件路径
        """
        # 合并内容并生成哈希
        content = entity_name + system_content + prompt_content
        hash_name = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # 改成 .kickoff_cache 目录
        return Path(".kickoff_cache") / self._game._name / f"{hash_name}.json"

    ###############################################################################################################################################
    async def _execute_kick_off_requests(self, entities: Set[Entity]) -> None:

        # 添加请求处理器
        chat_clients: List[ChatClient] = []

        for requesting_entity in entities:

            # 不同实体生成不同的提示
            kickoff_message_content = self._get_kick_off_message_content(
                requesting_entity
            )
            assert kickoff_message_content != "", "Generated prompt should not be empty"

            # 添加chat客户端
            agent_context = self._game.get_agent_context(requesting_entity)
            chat_clients.append(
                ChatClient(
                    name=requesting_entity.name,
                    prompt=kickoff_message_content,
                    context=agent_context.context,
                )
            )

        # 并发
        await ChatClient.gather_request_post(clients=chat_clients)

        # 添加上下文。
        for chat_client in chat_clients:

            processed_entity = self._game.get_entity_by_name(chat_client.name)
            assert processed_entity is not None

            # 整合聊天上下文
            self._prepend_kickoff_messages(
                processed_entity,
                chat_client.prompt,
                chat_client.response_ai_messages,
            )

            # 缓存启动响应
            self._cache_kick_off_response(
                processed_entity, chat_client.response_ai_messages
            )

            # 必须执行
            processed_entity.replace(
                KickOffDoneComponent,
                processed_entity.name,
                chat_client.response_content,
            )

            # 若是场景，用response替换environment描述
            if processed_entity.has(StageComponent):
                processed_entity.replace(
                    EnvironmentComponent,
                    processed_entity.name,
                    chat_client.response_content,
                )
            elif processed_entity.has(ActorComponent):
                pass

    ###############################################################################################################################################
    def _filter_valid_kick_off_entities(self) -> Set[Entity]:
        """
        筛选所有可以参与request处理的有效实体
        筛选条件：
        1. 包含 KickOffMessageComponent 且未包含 KickOffDoneComponent
        2. 必须是 Actor、Stage 或 WorldSystem 类型之一 (通过 Matcher.any_of 筛选)
        3. KickOffMessageComponent 的内容不为空
        """
        # 通过 Matcher 筛选：组件存在性 + 实体类型
        candidate_entities = self._game.get_group(
            Matcher(
                all_of=[KickOffComponent],
                any_of=[ActorComponent, StageComponent, WorldComponent],
                none_of=[KickOffDoneComponent],
            )
        ).entities.copy()

        valid_entities: Set[Entity] = set()

        for entity in candidate_entities:
            # 检查消息内容是否有效
            kick_off_message_comp = entity.get(KickOffComponent)
            if kick_off_message_comp is None or kick_off_message_comp.content == "":
                logger.warning(
                    f"KickOffSystem: {entity.name} kick off message is empty, skipping"
                )
                continue

            valid_entities.add(entity)

        return valid_entities

    ###############################################################################################################################################
    def _get_kick_off_message_content(self, entity: Entity) -> str:

        kick_off_message_comp = entity.get(KickOffComponent)
        assert kick_off_message_comp is not None
        assert (
            kick_off_message_comp.content != ""
        ), "KickOff message content should not be empty"
        return kick_off_message_comp.content

    ###############################################################################################################################################
