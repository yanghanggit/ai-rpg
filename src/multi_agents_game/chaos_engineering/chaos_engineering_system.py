from abc import ABC, abstractmethod
from ..entitas import Context


class IChaosEngineering(ABC):

    @abstractmethod
    def on_pre_new_game(self) -> None:
        pass

    @abstractmethod
    def on_post_new_game(self) -> None:
        pass

    @abstractmethod
    def initialize(self, execution_context: Context) -> None:
        pass
