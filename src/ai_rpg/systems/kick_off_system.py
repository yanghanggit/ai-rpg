from pathlib import Path
from typing import List, Set, final
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
    KickOffMessageComponent,
    StageComponent,
    WorldComponent,
)
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from ..game.config import LOGS_DIR


###############################################################################################################################################
@final
class KickOffSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: RPGGame, read_kick_off_cache: bool) -> None:
        self._game: RPGGame = game_context
        self._read_kick_off_cache: bool = read_kick_off_cache

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:

        # 处理请求
        valid_entities = self._get_valid_kick_off_entities()
        if len(valid_entities) == 0:
            return

        # cache pre-process，如果在logs目录下有缓存文件，则直接加载, 并从valid_entities中移除
        if self._read_kick_off_cache:
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
                    self._integrate_cache_chat_context(
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
    def _integrate_cache_chat_context(
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
        assert len(agent_context.context) == 1, "仅有一个system message!"
        assert agent_context.context[0].type == "system", "第一条必须是system message!"

        if (
            len(agent_context.context) == 1
            and agent_context.context[0].type == "system"
        ):
            # 确保类型正确的消息列表
            message_context_list: List[SystemMessage | HumanMessage | AIMessage] = [
                agent_context.context[0]  # system message
            ]

            # 添加human message
            message_context_list.append(
                HumanMessage(content=prompt, kickoff=entity.name)  # human message
            )

            # 添加AI messages
            message_context_list.extend(ai_messages)  # cache response ai messages

            # 移除原有的system message
            agent_context.context.pop(0)

            # 将新的上下文消息添加到聊天历史的开头
            agent_context.context = message_context_list + agent_context.context

            # 打印调试信息
            logger.warning(f"!cache human message: {entity.name} => \n{prompt}")
            for ai_msg in ai_messages:
                logger.warning(
                    f"!cache ai message: {entity.name} => \n{str(ai_msg.content)}"
                )

        else:
            assert False, "不应该走到这里!!!!!"

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

        return LOGS_DIR / f"{self._game._name}_kick_off_cache" / f"{hash_name}.json"

    ###############################################################################################################################################
    async def _execute_kick_off_requests(self, entities: Set[Entity]) -> None:

        # 添加请求处理器
        chat_clients: List[ChatClient] = []

        for entity1 in entities:
            # 不同实体生成不同的提示
            kickoff_message_content = self._get_kick_off_message_content(entity1)
            assert kickoff_message_content != "", "Generated prompt should not be empty"

            agent_context = self._game.get_agent_context(entity1)
            chat_clients.append(
                ChatClient(
                    name=entity1.name,
                    prompt=kickoff_message_content,
                    context=agent_context.context,
                )
            )

        # 并发
        await ChatClient.gather_request_post(clients=chat_clients)

        # 添加上下文。
        for chat_client in chat_clients:

            entity2 = self._game.get_entity_by_name(chat_client.name)
            assert entity2 is not None

            self._game.append_human_message(
                entity2, chat_client.prompt, kickoff=entity2.name
            )
            self._game.append_ai_message(entity2, chat_client.response_ai_messages)

            # 缓存启动响应
            self._cache_kick_off_response(entity2, chat_client.response_ai_messages)

            # 必须执行
            entity2.replace(
                KickOffDoneComponent, entity2.name, chat_client.response_content
            )

            # 若是场景，用response替换narrate
            if entity2.has(StageComponent):
                entity2.replace(
                    EnvironmentComponent,
                    entity2.name,
                    chat_client.response_content,
                )
            elif entity2.has(ActorComponent):
                pass

    ###############################################################################################################################################
    def _get_valid_kick_off_entities(self) -> Set[Entity]:
        """
        获取所有可以参与request处理的有效实体
        筛选条件：
        1. 包含 KickOffMessageComponent 且未包含 KickOffDoneComponent
        2. KickOffMessageComponent 的内容不为空
        3. 实体必须是 Actor、Stage 或 WorldSystem 类型之一
        """
        # 第一层筛选：基于组件存在性
        candidate_entities = self._game.get_group(
            Matcher(
                all_of=[KickOffMessageComponent],
                none_of=[KickOffDoneComponent],
            )
        ).entities.copy()

        valid_entities: Set[Entity] = set()

        for entity in candidate_entities:
            # 第二层筛选：检查消息内容
            kick_off_message_comp = entity.get(KickOffMessageComponent)
            if kick_off_message_comp is None or kick_off_message_comp.content == "":
                logger.warning(
                    f"KickOffSystem: {entity.name} kick off message is empty, skipping"
                )
                continue

            # 第三层筛选：检查实体类型
            if not (
                entity.has(ActorComponent)
                or entity.has(StageComponent)
                or entity.has(WorldComponent)
            ):
                logger.warning(
                    f"KickOffSystem: {entity.name} is not a valid entity type (Actor/Stage/WorldSystem), skipping"
                )
                continue

            valid_entities.add(entity)

        return valid_entities

    ###############################################################################################################################################
    def _get_kick_off_message_content(self, entity: Entity) -> str:

        kick_off_message_comp = entity.get(KickOffMessageComponent)
        assert kick_off_message_comp is not None
        assert (
            kick_off_message_comp.content != ""
        ), "KickOff message content should not be empty"
        return kick_off_message_comp.content

    ###############################################################################################################################################
