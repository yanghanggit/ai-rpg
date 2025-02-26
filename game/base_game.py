from abc import ABC, abstractmethod
from typing import Set
from rpg_models.event_models import BaseEvent


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

    @abstractmethod
    def send_message(self, player_proxy_names: Set[str], send_event: BaseEvent) -> None:
        pass
