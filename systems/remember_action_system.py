from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (RememberActionComponent)
from loguru import logger
from auxiliary.actor_action import ActorAction


class RememberActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(RememberActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(RememberActionComponent)
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.remember(entity)
###################################################################################################################
    def remember(self, entity: Entity) -> None:
        remembercomp: RememberActionComponent = entity.get(RememberActionComponent)
        action: ActorAction = remembercomp.action
        combine = action.combinevalues()
        logger.debug(f"debug!! [remember]:{action.name} = {combine}")
###################################################################################################################