from loguru import logger
from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from overrides import override
from typing import Any, Dict, List, cast, final
from game.tcg_game import TCGGame
from extended_systems.combat_system import CombatResult
from components.components_v_0_0_1 import ActorComponent, HeroComponent
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
        latest_combat = self._game.combat_system.latest_combat
        if not latest_combat.is_complete:
            # 不是本阶段就直接返回
            return

        if (
            latest_combat.result == CombatResult.HERO_WIN
            or latest_combat.result == CombatResult.HERO_LOSE
        ):
            # 测试，总结战斗结果。
            await self._summarize_combat_result()

            # 存储一下。
            self._game.save()

            # TODO, 退出游戏。
            latest_combat.post_combat_wait()

    #######################################################################################################################################
    async def _summarize_combat_result(self) -> None:
        # 获取所有需要进行角色规划的角色
        actor_entities = self._game.get_group(
            Matcher(
                all_of=[ActorComponent, HeroComponent],
            )
        ).entities

        # 处理角色规划请求
        request_handlers: List[ChatRequestHandler] = []
        for entity1 in actor_entities:

            stage_entity = self._game.safe_get_stage_entity(entity1)
            assert stage_entity is not None

            # 生成消息
            message = f"""# 提示！{stage_entity._name} 战斗结束，你决定记录下这次战斗的经历。
## 输出内容:
1. 战斗发生的场景。
2. 你的对手是谁，他们的特点。
3. 战斗的开始，过程以及如何结束的。
4. 你的感受，你的状态。
5. 你的同伴，他们的表现。
## 输出格式规范:
第一人称视角。
要求单段紧凑自述（禁用换行/空行/数字）。"""

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

        for request_handler in request_handlers:

            if request_handler.response_content == "":
                logger.error(f"Agent: {request_handler._name}, Response is empty.")
                continue

            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._game.append_human_message(
                entity2,
                request_handler._prompt,
            )
            self._game.append_ai_message(entity2, request_handler.response_content)

    #######################################################################################################################################
    # 总结战斗结果
    def _cache_combat_messages(self) -> None:
        actor_entities = self._game.get_group(
            Matcher(
                all_of=[ActorComponent, HeroComponent],
            )
        ).entities

        combat_message_cache: Dict[
            str, List[SystemMessage | HumanMessage | AIMessage]
        ] = {}

        for actor_entity in actor_entities:

            extracted_combat_messages = self._extract_last_combat_messages(actor_entity)

            logger.info(
                f"""{actor_entity._name} - find_messages: 
{"\n".join([m.model_dump_json() for m in extracted_combat_messages])}                        
"""
            )
            combat_message_cache[actor_entity._name] = extracted_combat_messages

    #######################################################################################################################################
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
