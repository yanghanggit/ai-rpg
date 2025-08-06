from typing import List, override

from ..entitas import CleanupProcessor, Entity, ReactiveProcessor
from ..game.tcg_game import TCGGame


####################################################################################################################################
class BaseActionReactiveSystem(ReactiveProcessor, CleanupProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context
        self._react_entities_copy: List[Entity] = []

    ####################################################################################################################################
    @override
    def cleanup(self) -> None:
        self._react_entities_copy.clear()

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        assert len(self._react_entities_copy) == 0
        self._react_entities_copy = entities.copy()
