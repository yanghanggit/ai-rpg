"""战斗回合清理系统：回合结束后清除旧回合手牌等瞬态状态，确保下一回合以干净状态启动。"""

from typing import Final, final, override
from loguru import logger
from ..entitas import ExecuteProcessor
from ..game.dbg_game import DBGGame


###############################################################################################################################################
@final
class CombatRoundCleanupSystem(ExecuteProcessor):
    """
    战斗回合清理系统：清除旧回合手牌状态（弃牌 + 重置回合动态属性）。
    """

    ############################################################################################################
    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.current_combat_room.combat.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，跳过旧回合手牌状态清除")
            return

        current_rounds = self._game.current_combat_room.combat.rounds or []
        if len(current_rounds) == 0:
            return

        last_round = self._game.current_combat_room.combat.latest_round
        assert last_round is not None, "latest_round is None"
        if not last_round.is_completed:
            return

        logger.debug("清除旧回合手牌状态")
        self._game.clear_round_state()
