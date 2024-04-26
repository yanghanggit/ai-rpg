
from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import AutoPlanningComponent, STAGE_AVAILABLE_ACTIONS_REGISTER, NPC_AVAILABLE_ACTIONS_REGISTER
from typing import Set
   
class PreActionSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  PreActionSystem  >>>>>>>>>>>>>>>>>")

        planningentities: Set[Entity] = self.context.get_group(Matcher(AutoPlanningComponent)).entities
        assert len(planningentities) == 0, "AutoPlanningComponent should be removed in PostPlanningSystem"

        stageentities = self.context.get_group(Matcher(any_of = STAGE_AVAILABLE_ACTIONS_REGISTER)).entities
        assert len(stageentities) == 0, f"Stage entities with actions: {stageentities}"

        npcentities = self.context.get_group(Matcher(any_of = NPC_AVAILABLE_ACTIONS_REGISTER)).entities
        assert len(npcentities) == 0, f"NPC entities with actions: {npcentities}"
############################################################################################################
   

