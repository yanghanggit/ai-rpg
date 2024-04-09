
from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import AutoPlanningComponent
from typing import Set

class PostPlanningSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  PostPlanningSystem  >>>>>>>>>>>>>>>>>")
        entities: Set[Entity] = self.context.get_group(Matcher(AutoPlanningComponent)).entities.copy()
        for entity in entities.copy():
            entity.remove(AutoPlanningComponent)
############################################################################################################

