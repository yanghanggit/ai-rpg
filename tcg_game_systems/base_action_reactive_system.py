from entitas import ReactiveProcessor, CleanupProcessor, Entity  # type: ignore
from game.tcg_game_context import TCGGameContext
from typing import cast, List, override
from game.tcg_game import TCGGame


####################################################################################################################################
class BaseActionReactiveSystem(ReactiveProcessor, CleanupProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        super().__init__(context)
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None
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
