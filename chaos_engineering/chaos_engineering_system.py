from abc import ABC, abstractmethod
from game.rpg_game_resource import RPGGameResource
from typing import Any, Optional


class IChaosEngineering(ABC):

    @abstractmethod
    def on_pre_create_game(
        self, extended_context: Any, game_resource: RPGGameResource
    ) -> None:
        pass

    @abstractmethod
    def on_post_create_game(
        self, extended_context: Any, game_resource: RPGGameResource
    ) -> None:
        pass

    @abstractmethod
    def on_read_memory_failed(
        self, extended_context: Any, name: str, prompt: str
    ) -> None:
        pass

    @abstractmethod
    def on_stage_planning_system_excute(self, extended_context: Any) -> None:
        pass

    @abstractmethod
    def on_actor_planning_system_execute(self, extended_context: Any) -> None:
        pass

    @abstractmethod
    def hack_stage_planning(
        self, extended_context: Any, stage_name: str, prompt: str
    ) -> Optional[str]:
        pass

    @abstractmethod
    def hack_actor_planning(
        self, extended_context: Any, actor_name: str, prompt: str
    ) -> Optional[str]:
        pass
