from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import override
from gameplay_systems.components import DestroyComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext


class DestroySystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        self._context: RPGEntitasContext = context

    ####################################################################################################################################
    @override
    def execute(self) -> None:
        entities = self._context.get_group(Matcher(DestroyComponent)).entities.copy()
        while len(entities) > 0:
            destory_entity = entities.pop()
            self._context.destroy_entity(destory_entity)

    ####################################################################################################################################
