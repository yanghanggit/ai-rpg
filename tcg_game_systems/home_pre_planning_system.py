from typing import final, cast
from entitas import ExecuteProcessor  # type: ignore
from overrides import override
from game.tcg_game import TCGGame


@final
class HomePrePlanningSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:
        pass

    ############################################################################################################
