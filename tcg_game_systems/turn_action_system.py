from entitas import Matcher, Entity, Matcher, GroupEvent  # type: ignore
from overrides import override
from typing import final
from components.actions_v_0_0_1 import TurnAction, SelectAction
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from components.components_v_0_0_1 import SkillCandidateQueueComponent
from models.v_0_0_1 import Skill


#######################################################################################################################################
@final
class TurnActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(TurnAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(TurnAction) and entity.has(SkillCandidateQueueComponent)

    #######################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        if len(self._react_entities_copy) == 0:
            return
        assert self._game.combat_system.is_on_going_phase

        # 开始新回合
        for actor_entity in self._react_entities_copy:

            turn_action = actor_entity.get(TurnAction)

            # 提示! 添加一个记忆
            self._game.append_human_message(
                entity=actor_entity,
                chat=f"# 提示！战斗回合开始，第 {turn_action.rounds} 回合！",
                combat_rounds=f"{turn_action.rounds}",
            )

            # 准备进入选择技能阶段！
            actor_entity.replace(
                SelectAction,
                actor_entity._name,
                [],
                Skill(name="", description="", effect=""),
                "",
                "",
            )

    #######################################################################################################################################
