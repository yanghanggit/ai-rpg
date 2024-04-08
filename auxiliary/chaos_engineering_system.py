from loguru import logger
from abc import ABC, abstractmethod
from auxiliary.builders import WorldDataBuilder
from typing import Any

##Used for testing, can simulate extreme situations, and can also be used to test system stability at runtime
class IChaosEngineering(ABC):
    #extended_context 不用Any会发生循环引用
    @abstractmethod
    def on_pre_create_world(self, extended_context: Any, worlddata: WorldDataBuilder) -> None:
        pass

    @abstractmethod
    def on_post_create_world(self, extended_context: Any, worlddata: WorldDataBuilder) -> None:
        pass

## 运行中的测试系统, 空的混沌工程系统
class ChaosEngineeringSystem(IChaosEngineering):
    ##
    def __init__(self, name: str) -> None:
        self.name: str = name

    ##
    def on_pre_create_world(self, extended_context: Any, worlddata: WorldDataBuilder) -> None:
        logger.debug(f"ChaosEngineeringSystem: {self.name} on_pre_create_world")

    ##
    def on_post_create_world(self, extended_context: Any, worlddata: WorldDataBuilder) -> None:
        logger.debug(f"ChaosEngineeringSystem: {self.name} on_post_create_world")
       

    