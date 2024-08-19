from abc import ABC, abstractmethod


# 基础类
class BaseGame(ABC):

    def __init__(self, name: str) -> None:
        self.name = name
        self.started: bool = False
        self.inited: bool = False
        self.exited: bool = False

    @abstractmethod
    def execute(self) -> None:
        pass

    @abstractmethod
    def exit(self) -> None:
        pass

    @abstractmethod
    async def async_execute(self) -> None:
        pass

    @abstractmethod
    def on_exit(self) -> None:
        pass
