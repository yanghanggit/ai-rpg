from typing import final, cast
from entitas import ExecuteProcessor  # type: ignore
from overrides import override
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame


@final
class PrePlanningSystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    ############################################################################################################
    @override
    def execute(self) -> None:
        pass

    ############################################################################################################
