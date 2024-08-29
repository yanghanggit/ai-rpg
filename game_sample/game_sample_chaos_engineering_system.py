#
import sys
from pathlib import Path

# 将项目根目录添加到sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
###
from chaos_engineering.chaos_engineering_system import IChaosEngineering

# from loguru import logger
from my_data.game_resource import GameResource
from typing import Any, Optional


## 运行中的测试系统, 空的混沌工程系统 my_chaos_engineering_system
class GameSampleChaosEngineeringSystem(IChaosEngineering):

    ##
    def __init__(self, name: str) -> None:
        self._name: str = name
        self._on_stage_system_excute_count = 0
        self._on_actor_system_excute_count = 0

    ##
    def on_pre_create_game(
        self, extended_context: Any, worlddata: GameResource
    ) -> None:
        pass
        # logger.warning(f" {self._name}: on_pre_create_world")

    ##
    def on_post_create_game(
        self, extended_context: Any, worlddata: GameResource
    ) -> None:
        pass
        # logger.warning(f" {self._name}: on_post_create_world")

    ##
    def on_read_memory_failed(
        self, extended_context: Any, name: str, readarchprompt: str
    ) -> None:
        pass
        # logger.debug(f"{self._name}: on_read_memory_failed {name} {readarchprompt}")

    ##
    def on_stage_planning_system_excute(self, extended_context: Any) -> None:
        pass
        # self._on_stage_system_excute_count += 1

    ##
    def on_actor_planning_system_execute(self, extended_context: Any) -> None:
        pass
        # self._on_actor_system_excute_count += 1

    ##
    def hack_stage_planning(
        self, extended_context: Any, stagename: str, planprompt: str
    ) -> Optional[str]:
        # from my_entitas.extended_context import ExtendedContext
        # context: ExtendedContext = extended_context
        return None

    ##
    def hack_actor_planning(
        self, extended_context: Any, actor_name: str, planprompt: str
    ) -> Optional[str]:
        # from my_entitas.extended_context import ExtendedContext
        # context: ExtendedContext = extended_context
        return None
