from entitas import ExecuteProcessor  # type: ignore
from typing import final, override
from game.tcg_game import TCGGame
from game.web_tcg_game import WebTCGGame


############################################################################################################
@final
class HandleWebPlayerInputSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:

        if not isinstance(self._game, WebTCGGame):
            return

    ############################################################################################################
