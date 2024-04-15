from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (LeaveForActionComponent, PrisonBreakActionComponent,
                        NPCComponent, 
                        StageEntryConditionComponent,
                        StageExitConditionComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from auxiliary.print_in_color import Color
from loguru import logger
from director_component import DirectorComponent
from director_event import LeaveForStageEvent, EnterStageEvent, FailEnterStageEvent, FailExitStageEvent
from typing import cast


###############################################################################################################################################
class PrisonBreakActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PrisonBreakActionComponent): GroupEvent.ADDED}

    def filter(self, entity: Entity) -> bool:
        return entity.has(PrisonBreakActionComponent)

    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  PrisonBreakActionSystem  >>>>>>>>>>>>>>>>>")
        self.prisonbreak(entities)

    def prisonbreak(self, entities: list[Entity]) -> None:
        pass
