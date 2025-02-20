from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import final, override, cast
from components.components import DestroyFlagComponent
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame


@final
class DestroySystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    ####################################################################################################################################
    @override
    def execute(self) -> None:
        entities = self._context.get_group(
            Matcher(DestroyFlagComponent)
        ).entities.copy()
        while len(entities) > 0:
            destory_entity = entities.pop()
            self._context.destroy_entity(destory_entity)

    ####################################################################################################################################
