from overrides import override
from entitas import InitializeProcessor, ExecuteProcessor # type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from typing import Dict

###############################################################################################################################################
class ActorUpdateAppearanceSystem(InitializeProcessor, ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
        self.tasks: Dict[str, str] = {}
###############################################################################################################################################
    @override
    def initialize(self) -> None:
        context = self.context
        #分段处理
        self.tasks.clear()
###############################################################################################################################################
    @override
    def execute(self) -> None:
        pass
####################################################################################################
    @override
    async def async_pre_execute(self) -> None:
        context = self.context
        agent_connect_system = context.agent_connect_system
        if len(self.tasks) == 0:
            return
        
        for name, prompt in self.tasks.items():
            agent_connect_system.add_async_request_task(name, prompt)

        await context.agent_connect_system.run_async_requet_tasks("ActorUpdateAppearanceSystem")
        self.tasks.clear() # 这句必须得走！！！
        logger.info("ActorUpdateAppearanceSystem done.")
###############################################################################################################################################
   
