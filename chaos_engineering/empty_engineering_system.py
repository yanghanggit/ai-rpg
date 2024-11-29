from game.rpg_game_resource import RPGGameResource
from typing import Any, Optional
from chaos_engineering.chaos_engineering_system import IChaosEngineering


class EmptyChaosEngineeringSystem(IChaosEngineering):

    def __init__(self, name: str = "") -> None:
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
        self, extended_context: Any, name: str, prompt: str
    ) -> None:
        pass

    def hack_stage_planning(
        self, extended_context: Any, stage_name: str, prompt: str
    ) -> Optional[str]:
        pass

    def hack_actor_planning(
        self, extended_context: Any, actor_name: str, prompt: str
    ) -> Optional[str]:
        pass

    def on_stage_planning_system_excute(self, extended_context: Any) -> None:
        pass

    def on_actor_planning_system_execute(self, extended_context: Any) -> None:
        pass
