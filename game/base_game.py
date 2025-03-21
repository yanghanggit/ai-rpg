from abc import ABC, abstractmethod


# 基础类，定义基本行为，其实是为了桥一下并做隔离
class BaseGame(ABC):

    def __init__(self, name: str) -> None:
        self._name = name
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
