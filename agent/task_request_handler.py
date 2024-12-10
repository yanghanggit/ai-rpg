from typing import Any, Optional
from abc import ABC, abstractmethod


class TaskRequestHandler(ABC):

    @abstractmethod
    def request(self) -> Optional[Any]:
        pass

    @abstractmethod
    async def a_request(self) -> Optional[Any]:
        pass
