from auxiliary.chaos_engineering_system import IChaosEngineering
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.builders import WorldDataBuilder

## 运行中的测试系统, 空的混沌工程系统
class ChaosBuddingWorld(IChaosEngineering):
    
    ##
    def __init__(self, name: str) -> None:
        self.name: str = name

    ##
    def on_pre_create_world(self, extended_context: ExtendedContext, worlddata: WorldDataBuilder) -> None:
        logger.debug(f"ChaosEngineeringSystem: {self.name} on_pre_create_world")

    ##
    def on_post_create_world(self, extended_context: ExtendedContext, worlddata: WorldDataBuilder) -> None:
        logger.debug(f"ChaosEngineeringSystem: {self.name} on_post_create_world")