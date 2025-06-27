from ..entitas import ExecuteProcessor
from typing import final, override
from ..game.tcg_game import TCGGame


@final
class HomePostSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:
        pass

    ############################################################################################################
