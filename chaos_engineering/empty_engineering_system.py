from loguru import logger
from my_data.game_resource import GameResource
from typing import Any, Optional
from chaos_engineering.chaos_engineering_system import IChaosEngineering


## 运行中的测试系统, 空的混沌工程系统
class EmptyChaosEngineeringSystem(IChaosEngineering):

    ##
    def __init__(self, name: str = "") -> None:
        self._name: str = name

    ##
    def on_pre_create_game(
        self, extended_context: Any, worlddata: GameResource
    ) -> None:
        pass
        # logger.debug(f" {self.name}: on_pre_create_world")

    ##
    def on_post_create_game(
        self, extended_context: Any, worlddata: GameResource
    ) -> None:
        pass
        # logger.debug(f"{self.name}: on_post_create_world")

    ##
    def on_read_memory_failed(
        self, extended_context: Any, name: str, readarchprompt: str
    ) -> None:
        logger.debug(f"{self._name}: on_read_memory_failed {name} {readarchprompt}")

    ##
    def hack_stage_planning(
        self, extended_context: Any, stagename: str, planprompt: str
    ) -> Optional[str]:
        logger.debug(f"{self._name}: hack_stage_planning {stagename} {planprompt}")
        return None

    ##
    def hack_actor_planning(
        self, extended_context: Any, actor_name: str, planprompt: str
    ) -> Optional[str]:
        logger.debug(f"{self._name}: hack_actor_planning {actor_name} {planprompt}")
        return None

    ##
    def on_stage_planning_system_excute(self, extended_context: Any) -> None:
        logger.debug(f"{self._name}: on_stage_planning_system_excute")

    ##
    def on_actor_planning_system_execute(self, extended_context: Any) -> None:
        logger.debug(f"{self._name}: on_actor_planning_system_execute")
