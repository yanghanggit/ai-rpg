from typing import final
from overrides import override
from ..entitas import ExecuteProcessor
from ..game.tcg_game import TCGGame
from loguru import logger


###############################################################################################################################################
@final
class SocialDeductionSeerSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        assert self._game._time_marker % 2 == 1, "时间标记必须是奇数，是夜晚"
        logger.info(f"夜晚 {self._game._time_marker // 2 + 1} 开始")
        logger.info("预言家请睁眼，选择你要查看的玩家")

    ###############################################################################################################################################

    # SEER = "seer"
    # WITCH = "witch"
