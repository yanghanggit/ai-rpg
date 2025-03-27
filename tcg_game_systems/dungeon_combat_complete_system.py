from loguru import logger
from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from overrides import override
from typing import Any, Dict, List, cast, final
from game.tcg_game import TCGGame
from extended_systems.combat_system import CombatResult
from components.components_v_0_0_1 import (
    ActorComponent,
    HeroComponent,
    CombatAttributesComponent,
)
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from extended_systems.chat_request_handler import ChatRequestHandler


#######################################################################################################################################
@final
class DungeonCombatCompleteSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:
        if not self._game.combat_system.is_complete_phase:
            return  # 不是本阶段就直接返回

        if (
            self._game.combat_system.combat_result == CombatResult.HERO_WIN
            or self._game.combat_system.combat_result == CombatResult.HERO_LOSE
        ):
            # 测试，总结战斗结果。
            await self._summarize_combat_result()

            # TODO, 进入战斗后准备的状态，离开当前状态。
            self._game.combat_system.combat_post_wait()

        else:
            assert False, "不可能出现的情况！"

    #######################################################################################################################################
    # 总结！！！
    async def _summarize_combat_result(self) -> None:
        # 获取所有需要进行角色规划的角色
        actor_entities = self._game.get_group(
            Matcher(
                all_of=[ActorComponent, HeroComponent, CombatAttributesComponent],
            )
        ).entities

        # 处理角色规划请求
        request_handlers: List[ChatRequestHandler] = []
        for entity1 in actor_entities:

            stage_entity1 = self._game.safe_get_stage_entity(entity1)
            assert stage_entity1 is not None

            # 生成消息
            message = f"""# 提示！{stage_entity1._name} 战斗结束，你决定记录下这次战斗的经历。
## 输出内容:
1. 战斗发生的场景。
2. 你的对手是谁，他们的特点。
3. 战斗的开始，过程以及如何结束的。
4. 你的感受，你的状态。
5. 你的同伴，他们的表现。
## 输出格式规范:
- 第一人称视角。
- 要求单段紧凑自述（禁用换行/空行/数字）。
- 尽量简短。"""

            # 生成请求处理器
            request_handlers.append(
                ChatRequestHandler(
                    name=entity1._name,
                    prompt=message,
                    chat_history=self._game.get_agent_short_term_memory(
                        entity1
                    ).chat_history,
                )
            )

        # 语言服务
        await self._game.langserve_system.gather(request_handlers=request_handlers)

        # 结束的处理。
        for request_handler in request_handlers:

            if request_handler.response_content == "":
                logger.error(f"Agent: {request_handler._name}, Response is empty.")
                continue

            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None

            stage_entity2 = self._game.safe_get_stage_entity(entity2)
            assert stage_entity2 is not None

            # 在这里做压缩！！先测试，可以不做。TODO。
            self._compress_chat_history_after_combat(entity2)

            # 压缩后的战斗经历，就是战斗过程做成摘要。
            summary = f"""# 发生事件! 你经历了一场战斗！
## 场景: {stage_entity2._name}
## 你记录下了这次战斗的经历:
{request_handler.response_content}"""

            # 添加记忆。
            self._game.append_human_message(
                entity=entity2,
                chat=summary,
                summarize_combat=f"{stage_entity2._name}",
            )

            #  # 准备记录～
            self._game.combat_system.last_combat.summarize_report[entity2._name] = (
                summary
            )

    #######################################################################################################################################
    # 压缩战斗历史。
    def _compress_chat_history_after_combat(self, entity: Entity) -> None:

        assert (
            entity.has(ActorComponent)
            and entity.has(HeroComponent)
            and entity.has(CombatAttributesComponent)
        )

        # 先获取最近的战斗消息。
        extracted_combat_messages = self._extract_last_combat_messages(entity)
        assert len(extracted_combat_messages) > 0
        if len(extracted_combat_messages) == 0:
            return

        # 以extracted_combat_messages[0]为标记，从short_term_memory.chat_history找到对应的位置。
        # 然后移除从extracted_combat_messages[0]到extracted_combat_messages[-1]之间的所有消息。
        short_term_memory = self._game.get_agent_short_term_memory(entity)
        start_index = short_term_memory.chat_history.index(extracted_combat_messages[0])
        end_index = (
            short_term_memory.chat_history.index(extracted_combat_messages[-1]) + 1
        )
        # 移除！！！！。
        del short_term_memory.chat_history[start_index:end_index]

    #######################################################################################################################################
    # 工具方法：提取最近的战斗消息。
    def _extract_last_combat_messages(
        self, actor_entity: Entity
    ) -> List[SystemMessage | HumanMessage | AIMessage]:

        extracted_combat_messages: List[SystemMessage | HumanMessage | AIMessage] = []
        is_combat_init_found = False

        chat_history = self._game.get_agent_short_term_memory(actor_entity).chat_history

        for chat_message in chat_history:
            if isinstance(chat_message, HumanMessage):
                kwargs = chat_message.model_dump()["kwargs"]
                if kwargs == None:
                    continue
                cast_dict = cast(Dict[str, Any], kwargs)
                if "combat_init_tag" in cast_dict:
                    is_combat_init_found = True

            if is_combat_init_found:
                extracted_combat_messages.append(chat_message)

        return extracted_combat_messages

    #######################################################################################################################################
