
from entitas import InitializeProcessor, ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
   
class BeginSystem(InitializeProcessor, ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def initialize(self) -> None:
        pass
############################################################################################################
    def execute(self) -> None:
        self.context.execute_count += 1
        logger.debug(f"世界执行次数：{self.context.execute_count}")
############################################################################################################

