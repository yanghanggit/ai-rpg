from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import final, override
from components.components import DestroyComponent
from game.rpg_entitas_context import RPGEntitasContext
from game.rpg_game import RPGGame


@final
class DestroyEntitySystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def execute(self) -> None:
        entities = self._context.get_group(Matcher(DestroyComponent)).entities.copy()
        while len(entities) > 0:
            destory_entity = entities.pop()
            self._context.destroy_entity(destory_entity)

    ####################################################################################################################################
