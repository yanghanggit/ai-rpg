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
    def __init__(self, name: str, localhost_urls: List[str]) -> None:

        # 名字
        self._name: Final[str] = name

        # 运行的服务器
        assert len(localhost_urls) > 0
        self._remote_runnables: Final[List[RemoteRunnable[Any, Any]]] = [
            RemoteRunnable(url=localhost_url) for localhost_url in localhost_urls
        ]

    ################################################################################################################################################################################
    async def gather(self, request_handlers: List[ChatRequestHandler]) -> List[Any]:

        if len(request_handlers) == 0:
            return []

        if len(self._remote_runnables) == 0:
            return []

        coros = []
        for idx, handler in enumerate(request_handlers):
            # 循环复用 RemoteRunnable
            runnable = self._remote_runnables[idx % len(self._remote_runnables)]
            coros.append(handler.a_request(runnable))

        # 允许异常捕获，不中断其他请求
        start_time = time.time()
        batch_results = await asyncio.gather(*coros, return_exceptions=True)
        end_time = time.time()
        logger.debug(f"task_request_utils.gather:{end_time - start_time:.2f} seconds")

        # 记录失败请求
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Request failed: {result}")

        return batch_results

    ################################################################################################################################################################################
    def handle(self, request_handlers: List[ChatRequestHandler]) -> None:

        if len(request_handlers) == 0:
            return

        if len(self._remote_runnables) == 0:
            return

        for request_handler in request_handlers:
            start_time = time.time()
            request_handler.request(self._remote_runnables[0])
            end_time = time.time()
            logger.debug(
                f"task_request_utils.handle:{end_time - start_time:.2f} seconds"
            )

    ################################################################################################################################################################################
