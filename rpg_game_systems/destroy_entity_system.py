from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import final, override
from components.components import DestroyComponent
from game.rpg_game_context import RPGGameContext
from game.rpg_game import RPGGame


@final
class DestroyEntitySystem(ExecuteProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def execute(self) -> None:
        entities = self._context.get_group(Matcher(DestroyComponent)).entities.copy()
        while len(entities) > 0:
            destory_entity = entities.pop()
            self._context.destroy_entity(destory_entity)

    ####################################################################################################################################
