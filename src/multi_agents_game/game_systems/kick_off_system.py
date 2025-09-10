from typing import List, Set, final

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

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:

        # 获取所有的舞台实体
        entities = self._game.get_group(
            Matcher(
                all_of=[KickOffMessageComponent],
                none_of=[KickOffDoneComponent],
            )
        ).entities.copy()

        if len(entities) == 0:
            return

        # 处理请求
        await self._process_request(entities)

    ###############################################################################################################################################
    async def _process_request(self, entities: Set[Entity]) -> None:

        # 添加请求处理器
        request_handlers: List[ChatClient] = []

        for entity1 in entities:
            # 不同实体生成不同的提示
            gen_prompt = self._generate_prompt(entity1)
            if gen_prompt == "":
                logger.error(
                    f"KickOffSystem: {entity1._name} kick off message is empty !!!!!!!"
                )
                continue

            agent_short_term_memory = self._game.get_agent_short_term_memory(entity1)
            request_handlers.append(
                ChatClient(
                    agent_name=entity1._name,
                    prompt=gen_prompt,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        # 并发
        await self._game.chat_system.gather(request_handlers=request_handlers)

        # 添加上下文。
        for request_handler in request_handlers:

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None

            agent_short_term_memory = self._game.get_agent_short_term_memory(entity2)
            if (
                len(agent_short_term_memory.chat_history) > 0
                and agent_short_term_memory.chat_history[0].type == "system"
            ):

                # 确保类型正确的消息列表
                contextual_message_list: List[
                    SystemMessage | HumanMessage | AIMessage
                ] = []

                # 添加原有的system message（确保类型匹配）
                first_message = agent_short_term_memory.chat_history[0]
                if isinstance(first_message, (SystemMessage, HumanMessage, AIMessage)):
                    contextual_message_list.append(first_message)

                # 添加human message
                contextual_message_list.append(
                    HumanMessage(content=request_handler._prompt)
                )

                # 添加AI messages
                contextual_message_list.extend(request_handler.ai_messages)

                agent_short_term_memory.chat_history.pop(0)  # 移除原有的system message
                # 将新的上下文消息添加到聊天历史的开头
                agent_short_term_memory.chat_history = (
                    contextual_message_list + agent_short_term_memory.chat_history
                )
            else:
                # 常规添加。
                self._game.append_human_message(entity2, request_handler._prompt)
                self._game.append_ai_message(entity2, request_handler.ai_messages)

            # 必须执行
            entity2.replace(
                KickOffDoneComponent, entity2._name, request_handler.response_content
            )

            # 若是场景，用response替换narrate
            if entity2.has(StageComponent):
                entity2.replace(
                    EnvironmentComponent,
                    entity2._name,
                    request_handler.response_content,
                )
            elif entity2.has(ActorComponent):
                pass

    ###############################################################################################################################################
    def _generate_prompt(self, entity: Entity) -> str:

        kick_off_message_comp = entity.get(KickOffMessageComponent)
        assert kick_off_message_comp is not None
        if kick_off_message_comp.content == "":
            return ""

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
