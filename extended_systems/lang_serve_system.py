from loguru import logger
from typing import Final, List, Any, final
from langserve import RemoteRunnable
from typing import List, Any
from loguru import logger
import asyncio
import time
from extended_systems.chat_request_handler import ChatRequestHandler


@final
class LangServeSystem:

    ################################################################################################################################################################################
    def __init__(
        self,
        name: str,
        url: str,
    ) -> None:

        # 名字
        self._name: Final[str] = name

        # TODO, 后续可以考虑弄的复杂一点
        self._remote_runnable: Final[RemoteRunnable[Any, Any]] = RemoteRunnable(url=url)

    ################################################################################################################################################################################
    async def gather(self, request_handlers: List[ChatRequestHandler]) -> List[Any]:
        if len(request_handlers) == 0:
            return []

        coros = [task.a_request(self._remote_runnable) for task in request_handlers]

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
            request_handler.request(self._remote_runnable)

    ################################################################################################################################################################################
