from typing import List, Set, final
from loguru import logger
from overrides import override
from ..chat_services.client import ChatClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.sd_game import SDGame
from ..models import (
    ActorComponent,
    EnvironmentComponent,
    KickOffDoneComponent,
    KickOffMessageComponent,
    StageComponent,
    WorldComponent,
    PlayerComponent,
)
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


###############################################################################################################################################
def _generate_actor_prompt(kick_off_message: str) -> str:
    return f"""# 游戏启动! 你将开始你的扮演。你将以此为初始状态，开始你的冒险。

## 这是你的启动消息

{kick_off_message}

## 输出要求

- 你的内心活动，单段紧凑自述（禁用换行/空行）"""


###############################################################################################################################################
def _generate_stage_prompt(
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
def _generate_world_system_prompt() -> str:
    return f"""# 游戏启动! 你将开始你的扮演。你将以此为初始状态，开始你的冒险。

## 这是你的启动消息

- 请回答你的职能与描述。

## 输出要求

- 确认你的职能，单段紧凑自述（禁用换行/空行）"""


###############################################################################################################################################


###############################################################################################################################################
@final
class SDKickOffSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: SDGame) -> None:
        self._game: SDGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:

        # 处理请求
        valid_entities = self._get_valid_kick_off_entities()
        if len(valid_entities) == 0:
            return

        # 处理请求
        await self._process_request(valid_entities)

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
        agent_short_term_memory = self._game.get_agent_chat_history(entity)

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
            contextual_message_list.append(
                HumanMessage(content=prompt, kickoff=entity.name)
            )

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
            self._game.append_human_message(entity, prompt, kickoff=entity.name)
            self._game.append_ai_message(entity, ai_messages)

    ###############################################################################################################################################
    async def _process_request(self, entities: Set[Entity]) -> None:

        # 添加请求处理器
        request_handlers: List[ChatClient] = []

        for entity1 in entities:
            # 不同实体生成不同的提示
            gen_prompt = self._generate_prompt(entity1)
            assert gen_prompt != "", "Generated prompt should not be empty"

            agent_short_term_memory = self._game.get_agent_chat_history(entity1)
            request_handlers.append(
                ChatClient(
                    name=entity1.name,
                    prompt=gen_prompt,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        # 并发
        await ChatClient.gather_request_post(clients=request_handlers)

        # 添加上下文。
        for request_handler in request_handlers:

            entity2 = self._game.get_entity_by_name(request_handler.name)
            assert entity2 is not None

            # 使用封装的函数整合聊天上下文
            self._integrate_chat_context(
                entity2, request_handler.prompt, request_handler.response_ai_messages
            )

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
                none_of=[KickOffDoneComponent, PlayerComponent],
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
    def _generate_prompt(self, entity: Entity) -> str:

        kick_off_message_comp = entity.get(KickOffMessageComponent)
        assert kick_off_message_comp is not None
        assert (
            kick_off_message_comp.content != ""
        ), "KickOff message content should not be empty"

        # 不同实体生成不同的提示
        if entity.has(ActorComponent):
            # 角色的
            return _generate_actor_prompt(kick_off_message_comp.content)
        elif entity.has(StageComponent):
            # 舞台的
            return _generate_stage_prompt(
                kick_off_message_comp.content,
            )
        elif entity.has(WorldComponent):
            # 世界系统的
            return _generate_world_system_prompt()

        return ""

    ###############################################################################################################################################
