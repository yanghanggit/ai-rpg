#
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from game.rpg_game_resource import RPGGameResource
from typing import Any, Optional


class GameSampleChaosEngineeringSystem(IChaosEngineering):

    def __init__(self, name: str) -> None:
        self._name: str = name

    def on_pre_create_game(
        self, extended_context: Any, game_resource: RPGGameResource
    ) -> None:
        pass

    def on_post_create_game(
        self, extended_context: Any, game_resource: RPGGameResource
    ) -> None:
        pass

    def on_read_memory_failed(
        self, extended_context: Any, name: str, readarchprompt: str
    ) -> None:
        pass

    def on_stage_planning_system_excute(self, extended_context: Any) -> None:
        pass

    def on_actor_planning_system_execute(self, extended_context: Any) -> None:
        pass

    def hack_stage_planning(
        self, extended_context: Any, stage_name: str, prompt: str
    ) -> Optional[str]:
        return None

    def hack_actor_planning(
        self, extended_context: Any, actor_name: str, prompt: str
    ) -> Optional[str]:
        return None
