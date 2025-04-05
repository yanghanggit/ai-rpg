from abc import ABC, abstractmethod
from typing import Any


class IChaosEngineering(ABC):

    @abstractmethod
    def on_pre_new_game(self) -> None:
        pass

    @abstractmethod
    def on_post_new_game(self) -> None:
        pass

    @abstractmethod
    def initialize(self, execution_context: Any) -> None:
        pass
