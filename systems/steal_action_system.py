from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (  StealActionComponent,
                                    NPCComponent)
from loguru import logger
class StealActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(StealActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(StealActionComponent) and entity.has(NPCComponent)
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  StealActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.steal(entity)
###################################################################################################################
    def steal(self, entity: Entity) -> None:
        safename = self.context.safe_get_entity_name(entity)
        logger.debug(f"StealActionSystem: {safename} is stealing")
        pass
###################################################################################################################