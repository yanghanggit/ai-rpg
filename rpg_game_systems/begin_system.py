from entitas import ExecuteProcessor  # type: ignore
from typing import final, override
from game.rpg_game_context import RPGGameContext
from game.rpg_game import RPGGame


@final
class BeginSystem(ExecuteProcessor):
    ############################################################################################################
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        pass
