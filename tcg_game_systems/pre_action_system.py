from entitas import ExecuteProcessor  # type: ignore
from typing import final, override, cast
from game.tcg_game import TCGGame
from game.tcg_game_context import TCGGameContext


@final
class PreActionSystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    @override
    def execute(self) -> None:
        pass
