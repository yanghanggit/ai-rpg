from abc import ABC, abstractmethod

#基础类
class BaseGame(ABC):

    def __init__(self, name: str) -> None:
        self.name = name
        self.started: bool = False
        self.inited: bool = False
         
    @abstractmethod
    def execute(self) -> None:
        pass

    @abstractmethod
    def exit(self) -> None:
        pass


