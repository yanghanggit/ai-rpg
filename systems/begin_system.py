
from entitas import InitializeProcessor, ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
   
class BeginSystem(InitializeProcessor, ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def initialize(self) -> None:
        logger.debug("<<<<<<<<<<<<<  BeginSystem.initialize  >>>>>>>>>>>>>>>>>")
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  BeginSystem.execute  >>>>>>>>>>>>>>>>>")
############################################################################################################

