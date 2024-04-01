from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import TagActionComponent
from auxiliary.extended_context import ExtendedContext
from loguru import logger

####################################################################################################
class TagActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(TagActionComponent): GroupEvent.ADDED}
####################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(TagActionComponent)
####################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  TagActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            entity.remove(TagActionComponent)    
####################################################################################################