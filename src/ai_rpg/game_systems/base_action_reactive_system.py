from typing import override
from ..entitas import CleanupProcessor, ReactiveProcessor
from ..game.tcg_game import TCGGame


####################################################################################################################################
class BaseActionReactiveSystem(ReactiveProcessor, CleanupProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

    ####################################################################################################################################
    @override
    def cleanup(self) -> None:
        pass

    ####################################################################################################################################
