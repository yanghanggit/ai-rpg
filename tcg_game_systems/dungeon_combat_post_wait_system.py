from loguru import logger
from entitas import ExecuteProcessor  # type: ignore
from overrides import override
from typing import final
from game.tcg_game import TCGGame


#######################################################################################################################################
@final
class DungeonCombatPostWaitSystem(ExecuteProcessor):

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
        if not latest_combat.is_post_wait:
            # 不是本阶段就直接返回
            return
        logger.info(
            "DungeonCombatPostWaitSystem: POST_WAIT!!!!!! 等待返回或者继续打下一局！！！！"
        )

    #######################################################################################################################################
