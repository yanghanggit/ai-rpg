from entitas import Matcher, Entity, Matcher, GroupEvent  # type: ignore
from overrides import override
from typing import final
from components.actions2 import TurnAction2
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from extended_systems.combat_system import CombatState


#######################################################################################################################################
@final
class TurnActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(TurnAction2): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(TurnAction2)

    #######################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        if len(self._react_entities_copy) == 0:
            return

        assert (
            self._game.combat_system.latest_combat.current_state == CombatState.RUNNING
        )

        # 开始新回合
        latest_combat = self._game.combat_system.latest_combat

        # 提示!
        for actor_entity in self._react_entities_copy:
            self._game.append_human_message(
                entity=actor_entity,
                chat=f"# 提示！战斗回合开始 = {len(latest_combat.rounds)}",
                tag=f"battle:{latest_combat._name}:{len(latest_combat.rounds)}",
            )

    #######################################################################################################################################
