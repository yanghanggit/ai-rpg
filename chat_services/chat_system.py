from loguru import logger
from typing import Final, List, Any, final
import httpx
import asyncio
import asyncio
import time
from chat_services.chat_request_handler import ChatRequestHandler


@final
class ChatSystem:

    ################################################################################################################################################################################
    def __init__(self, name: str, user_name: str, localhost_urls: List[str]) -> None:

        # 名字
        self._name: Final[str] = name

        self._user_name: Final[str] = user_name

        # 运行的服务器
        assert len(localhost_urls) > 0
        self._localhost_urls: Final[List[str]] = localhost_urls

        # 异步请求客户端
        self._async_client: Final[httpx.AsyncClient] = httpx.AsyncClient()

    ################################################################################################################################################################################
    async def gather(self, request_handlers: List[ChatRequestHandler]) -> List[Any]:

        if len(request_handlers) == 0:
            return []

        if len(self._localhost_urls) == 0:
            return []

        coros = []
        for idx, handler in enumerate(request_handlers):
            # 循环复用
            endpoint_url = self._localhost_urls[idx % len(self._localhost_urls)]
            handler._user_name = self._user_name
            coros.append(handler.a_request(self._async_client, endpoint_url))

        # 允许异常捕获，不中断其他请求
        start_time = time.time()
        batch_results = await asyncio.gather(*coros, return_exceptions=True)
        end_time = time.time()
        logger.debug(f"ChatSystem.gather:{end_time - start_time:.2f} seconds")

        # 记录失败请求
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Request failed: {result}")

        return batch_results

    ################################################################################################################################################################################
    def handle(self, request_handlers: List[ChatRequestHandler]) -> None:

        if len(request_handlers) == 0:
            return

        if len(self._localhost_urls) == 0:
            return

        for request_handler in request_handlers:
            start_time = time.time()
            request_handler._user_name = self._user_name
            request_handler.request(self._localhost_urls[0])
            end_time = time.time()
            logger.debug(f"ChatSystem.handle:{end_time - start_time:.2f} seconds")

    ################################################################################################################################################################################
