
from entitas import ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
   
class BeginSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  BeginSystem  >>>>>>>>>>>>>>>>>")
############################################################################################################

