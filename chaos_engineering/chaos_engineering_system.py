from loguru import logger
from abc import ABC, abstractmethod
from build_game.game_builder import GameBuilder
from typing import Any, Optional

##Used for testing, can simulate extreme situations, and can also be used to test system stability at runtime
class IChaosEngineering(ABC):
    #extended_context 不用Any会发生循环引用
    @abstractmethod
    def on_pre_create_game(self, extended_context: Any, worlddata: GameBuilder) -> None:
        pass

    @abstractmethod
    def on_post_create_game(self, extended_context: Any, worlddata: GameBuilder) -> None:
        pass

    @abstractmethod  
    def on_read_memory_failed(self, extended_context: Any, name: str, readarchprompt: str) -> None:
        pass

    @abstractmethod  
    def on_stage_planning_system_excute(self, extended_context: Any) -> None:
        pass

    @abstractmethod  
    def on_actor_planning_system_execute(self, extended_context: Any) -> None:
        pass

    @abstractmethod  
    def hack_stage_planning(self, extended_context: Any, stagename: str, planprompt: str) -> Optional[str]:
        pass

    @abstractmethod
    def hack_actor_planning(self, extended_context: Any, actor_name: str, planprompt: str) -> Optional[str]:
        pass

       

    