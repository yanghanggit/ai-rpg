from pathlib import Path
from typing import List, Set, final
import json
import hashlib
from loguru import logger
from overrides import override
from ..chat_services.client import ChatClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    EnvironmentComponent,
    KickOffDoneComponent,
    KickOffMessageComponent,
    StageComponent,
    WorldSystemComponent,
)
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from ..game.game_config import LOGS_DIR


###############################################################################################################################################
def _generate_actor_kick_off_prompt(kick_off_message: str) -> str:
    return f"""# 游戏启动! 你将开始你的扮演。你将以此为初始状态，开始你的冒险。

## 这是你的启动消息

{kick_off_message}

## 输出要求

- 你的内心活动，单段紧凑自述（禁用换行/空行）"""


###############################################################################################################################################
def _generate_stage_kick_off_prompt(
    kick_off_message: str,
) -> str:
    return f"""# 游戏启动! 你将开始你的扮演。你将以此为初始状态，开始你的冒险。

## 这是你的启动消息

{kick_off_message}

## 输出内容-场景描述

- 场景内的环境描述，不要包含任何角色信息。

## 输出要求

- 输出场景描述，单段紧凑自述（禁用换行/空行）。
- 输出必须为第三人称视角。"""


###############################################################################################################################################
def _generate_world_system_kick_off_prompt() -> str:
    return f"""# 游戏启动! 你将开始你的扮演。你将以此为初始状态，开始你的冒险。

## 这是你的启动消息

- 请回答你的职能与描述。

## 输出要求

- 确认你的职能，单段紧凑自述（禁用换行/空行）"""


###############################################################################################################################################


###############################################################################################################################################
@final
class KickOffSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context
        self._read_kick_off_cache: bool = True

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
            logger.info(
                "KickOffSystem: All entities loaded from cache, no new requests needed"
            )
            return

        # 处理请求
        await self._process_request(entities_to_process)

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
            prompt = self._generate_prompt(entity)
            cache_path = self._get_kick_off_cache_path(
                entity.name, system_content, prompt
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
                    self._integrate_chat_context(entity, prompt, ai_messages)

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

                    logger.info(
                        f"KickOffSystem: Loaded cached response for {entity.name}"
                    )

                except Exception as e:
                    logger.warning(
                        f"KickOffSystem: Failed to load cache for {entity.name}: {e}, will process normally"
                    )
                    # 如果加载缓存失败，保留在待处理集合中

        return entities_to_process

    ###############################################################################################################################################
    def _integrate_chat_context(
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
        agent_short_term_memory = self._game.get_agent_short_term_memory(entity)

        if (
            len(agent_short_term_memory.chat_history) > 0
            and agent_short_term_memory.chat_history[0].type == "system"
        ):
            # 确保类型正确的消息列表
            contextual_message_list: List[SystemMessage | HumanMessage | AIMessage] = []

            # 添加原有的system message（确保类型匹配）
            first_message = agent_short_term_memory.chat_history[0]
            if isinstance(first_message, (SystemMessage, HumanMessage, AIMessage)):
                contextual_message_list.append(first_message)

            # 添加human message
            contextual_message_list.append(HumanMessage(content=prompt))

            # 添加AI messages
            contextual_message_list.extend(ai_messages)

            # 移除原有的system message
            agent_short_term_memory.chat_history.pop(0)

            # 将新的上下文消息添加到聊天历史的开头
            agent_short_term_memory.chat_history = (
                contextual_message_list + agent_short_term_memory.chat_history
            )

            # 打印调试信息
            logger.debug(
                f"integrate_chat_context human message: {entity.name} => \n{prompt}"
            )
            for ai_msg in ai_messages:
                logger.debug(
                    f"integrate_chat_context ai message: {entity.name} => \n{str(ai_msg.content)}"
                )

        else:
            # 常规添加
            self._game.append_human_message(entity, prompt)
            self._game.append_ai_message(entity, ai_messages)

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
            prompt_content = self._generate_prompt(entity)

            # 构建基于内容哈希的文件路径
            path = self._get_kick_off_cache_path(
                entity.name, system_content, prompt_content
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
        agent_memory = self._game.get_agent_short_term_memory(entity)
        if (
            len(agent_memory.chat_history) > 0
            and agent_memory.chat_history[0].type == "system"
        ):
            return str(agent_memory.chat_history[0].content)
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
    async def _process_request(self, entities: Set[Entity]) -> None:

        # 添加请求处理器
        request_handlers: List[ChatClient] = []

        for entity1 in entities:
            # 不同实体生成不同的提示
            gen_prompt = self._generate_prompt(entity1)
            assert gen_prompt != "", "Generated prompt should not be empty"

            agent_short_term_memory = self._game.get_agent_short_term_memory(entity1)
            request_handlers.append(
                ChatClient(
                    name=entity1.name,
                    prompt=gen_prompt,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        # 并发
        # await self._game.chat_client_manager.gather(
        #     request_handlers=request_handlers,
        #     # options=ChatApiEndpointOptions.DEEPSEEK_MCP_CHAT,
        # )
        await ChatClient.gather_request_post(clients=request_handlers)

        # 添加上下文。
        for request_handler in request_handlers:

            entity2 = self._game.get_entity_by_name(request_handler.name)
            assert entity2 is not None

            # 使用封装的函数整合聊天上下文
            self._integrate_chat_context(
                entity2, request_handler.prompt, request_handler.response_ai_messages
            )

            # 缓存启动响应
            self._cache_kick_off_response(entity2, request_handler.response_ai_messages)

            # 必须执行
            entity2.replace(
                KickOffDoneComponent, entity2.name, request_handler.response_content
            )

            # 若是场景，用response替换narrate
            if entity2.has(StageComponent):
                entity2.replace(
                    EnvironmentComponent,
                    entity2.name,
                    request_handler.response_content,
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
                or entity.has(WorldSystemComponent)
            ):
                logger.warning(
                    f"KickOffSystem: {entity.name} is not a valid entity type (Actor/Stage/WorldSystem), skipping"
                )
                continue

            valid_entities.add(entity)

        return valid_entities

    ###############################################################################################################################################
    def _generate_prompt(self, entity: Entity) -> str:

        kick_off_message_comp = entity.get(KickOffMessageComponent)
        assert kick_off_message_comp is not None
        assert (
            kick_off_message_comp.content != ""
        ), "KickOff message content should not be empty"

        # 不同实体生成不同的提示
        if entity.has(ActorComponent):
            # 角色的
            return _generate_actor_kick_off_prompt(kick_off_message_comp.content)
        elif entity.has(StageComponent):
            # 舞台的
            return _generate_stage_kick_off_prompt(
                kick_off_message_comp.content,
            )
        elif entity.has(WorldSystemComponent):
            # 世界系统的
            return _generate_world_system_kick_off_prompt()

        return ""

    ###############################################################################################################################################
