from typing import override
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from gameplay_systems.action_components import TagAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger


####################################################################################################
class TagActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context

    ####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(TagAction): GroupEvent.ADDED}

    ####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(TagAction)

    ####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        pass


####################################################################################################
