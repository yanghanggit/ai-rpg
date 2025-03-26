from entitas import ExecuteProcessor  # type: ignore
from typing import final, override
from game.tcg_game import TCGGame


@final
class BeginSystem(ExecuteProcessor):
    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:
        self._game._debug_flag_pipeline = True

    ############################################################################################################
