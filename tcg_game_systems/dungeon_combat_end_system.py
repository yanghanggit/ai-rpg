from loguru import logger
from entitas import ExecuteProcessor  # type: ignore
from overrides import override
from typing import final
from game.tcg_game import TCGGame
from extended_systems.combat_system import CombatState, CombatResult


#######################################################################################################################################
@final
class DungeonCombatEndSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:

        latest_combat = self._game.combat_system.latest_combat

        if latest_combat.current_state != CombatState.END:
            # 不是本阶段就直接返回
            return

        if latest_combat.result == CombatResult.WIN:
            logger.info("DungeonCombatEndSystem: WIN")
        elif latest_combat.result == CombatResult.LOSE:
            logger.info("DungeonCombatEndSystem: LOSE")
        else:
            logger.info("DungeonCombatEndSystem: UNKNOWN")

    #######################################################################################################################################
