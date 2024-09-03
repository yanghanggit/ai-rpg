from abc import ABC, abstractmethod


# 基础类
class BaseGame(ABC):

    def __init__(self, name: str) -> None:
        self._name = name
        self._started: bool = False
        self._will_exit: bool = False

    @abstractmethod
    def execute(self) -> None:
        pass

    @abstractmethod
    async def a_execute(self) -> None:
        pass

    @abstractmethod
    def exit(self) -> None:
        pass
