from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (  TradeActionComponent,
                                    NPCComponent)
from loguru import logger
class TradeActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(TradeActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(TradeActionComponent) and entity.has(NPCComponent)
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  TradeActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.trade(entity)
###################################################################################################################
    def trade(self, entity: Entity) -> None:
        safename = self.context.safe_get_entity_name(entity)
        logger.debug(f"TradeActionSystem: {safename} is trading")
        pass
###################################################################################################################