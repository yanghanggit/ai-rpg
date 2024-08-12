from typing import override
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from ecs_systems.action_components import TagActionComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger

####################################################################################################
class TagActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context = context
####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(TagActionComponent): GroupEvent.ADDED}
####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(TagActionComponent)
####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        pass
####################################################################################################