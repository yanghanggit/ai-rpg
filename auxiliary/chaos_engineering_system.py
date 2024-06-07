from loguru import logger
from abc import ABC, abstractmethod
from auxiliary.builders import WorldDataBuilder
from typing import Any, Optional

##Used for testing, can simulate extreme situations, and can also be used to test system stability at runtime
class IChaosEngineering(ABC):
    #extended_context 不用Any会发生循环引用
    @abstractmethod
    def on_pre_create_game(self, extended_context: Any, worlddata: WorldDataBuilder) -> None:
        pass

    @abstractmethod
    def on_post_create_game(self, extended_context: Any, worlddata: WorldDataBuilder) -> None:
        pass

    @abstractmethod  
    def on_read_memory_failed(self, extended_context: Any, name: str, readarchprompt: str) -> None:
        pass

    @abstractmethod  
    def on_stage_planning_system_excute(self, extended_context: Any) -> None:
        pass

    @abstractmethod  
    def on_npc_planning_system_execute(self, extended_context: Any) -> None:
        pass

    @abstractmethod  
    def hack_stage_planning(self, extended_context: Any, stagename: str, planprompt: str) -> Optional[str]:
        pass

    @abstractmethod
    def hack_npc_planning(self, extended_context: Any, npcname: str, planprompt: str) -> Optional[str]:
        pass

## 运行中的测试系统, 空的混沌工程系统
class EmptyChaosEngineeringSystem(IChaosEngineering):
    
    ##
    def __init__(self, name: str) -> None:
        self.name: str = name

    ##
    def on_pre_create_game(self, extended_context: Any, worlddata: WorldDataBuilder) -> None:
        logger.debug(f" {self.name}: on_pre_create_world")

    ##
    def on_post_create_game(self, extended_context: Any, worlddata: WorldDataBuilder) -> None:
        logger.debug(f"{self.name}: on_post_create_world")

    ##
    def on_read_memory_failed(self, extended_context: Any, name: str, readarchprompt: str) -> None:
        logger.debug(f"{self.name}: on_read_memory_failed {name} {readarchprompt}")

    ##
    def hack_stage_planning(self, extended_context: Any, stagename: str, planprompt: str) -> Optional[str]:
        logger.debug(f"{self.name}: hack_stage_planning {stagename} {planprompt}")
        return None

    ##
    def hack_npc_planning(self, extended_context: Any, npcname: str, planprompt: str) -> Optional[str]:
        logger.debug(f"{self.name}: hack_npc_planning {npcname} {planprompt}")
        return None
    
    ##
    def on_stage_planning_system_excute(self, extended_context: Any) -> None:
        logger.debug(f"{self.name}: on_stage_planning_system_excute")

    ##
    def on_npc_planning_system_execute(self, extended_context: Any) -> None:
        logger.debug(f"{self.name}: on_npc_planning_system_execute")
       

    