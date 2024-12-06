from abc import ABC, abstractmethod
from typing import Any


class IChaosEngineering(ABC):

    @abstractmethod
    def on_pre_create_game(self) -> None:
        pass

    @abstractmethod
    def on_post_create_game(self) -> None:
        pass

    @abstractmethod
    def initialize(self, execution_context: Any) -> None:
        pass
