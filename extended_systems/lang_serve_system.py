from loguru import logger
from typing import List, Any, Optional
from langserve import RemoteRunnable
from typing import List, Any
from loguru import logger
import asyncio
import time
from extended_systems.chat_request_handler import ChatRequestHandler


class LangServeSystem:

    ################################################################################################################################################################################
    def __init__(
        self,
        name: str,
    ) -> None:

        # 名字
        self._name = name

        # todo 后续可以变的复杂一些
        self._remote_runnable: Optional[RemoteRunnable[Any, Any]] = None

    ################################################################################################################################################################################
    def add_remote_runnable(self, url: str) -> None:
        assert self._remote_runnable is None
        assert url != ""
        self._remote_runnable = RemoteRunnable(url=url)

    ################################################################################################################################################################################
    @property
    def remote_runnable(self) -> RemoteRunnable[Any, Any]:
        assert self._remote_runnable is not None
        return self._remote_runnable

    ################################################################################################################################################################################
    async def gather(self, request_handlers: List[ChatRequestHandler]) -> List[Any]:
        if len(request_handlers) == 0:
            return []

        coros = [task.a_request(self.remote_runnable) for task in request_handlers]

        start_time = time.time()
        future = await asyncio.gather(*coros)
        end_time = time.time()

        logger.debug(f"task_request_utils.gather:{end_time - start_time:.2f} seconds")
        return future

    ################################################################################################################################################################################
    def handle(self, request_handlers: List[ChatRequestHandler]) -> None:
        if len(request_handlers) == 0:
            return

        for request_handler in request_handlers:
            request_handler.request(self.remote_runnable)

    ################################################################################################################################################################################
