
from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import AutoPlanningComponent, StageComponent, NPCComponent, PlayerComponent
   
class PreActionSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  PreActionSystem  >>>>>>>>>>>>>>>>>")
############################################################################################################
   

