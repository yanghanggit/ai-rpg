from ..entitas import ExecuteProcessor
from typing import final, override
from ..game.tcg_game import TCGGame


@final
class EndSystem(ExecuteProcessor):
    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:
        assert self._game._debug_flag_pipeline is True
        self._game._debug_flag_pipeline = False

    ############################################################################################################
