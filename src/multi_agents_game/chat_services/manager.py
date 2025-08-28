import asyncio
import time
from typing import Final, List, final

import httpx
from loguru import logger

from .client import ChatClient


@final
class ChatClientManager:

    ################################################################################################################################################################################
    def __init__(self, name: str, localhost_urls: List[str]) -> None:

        # 名字
        self._name: Final[str] = name

        # self._username: Final[str] = username

        # 运行的服务器
        assert len(localhost_urls) > 0
        self._chat_server_localhost_urls: Final[List[str]] = localhost_urls

        # 异步请求客户端
        self._async_client: Final[httpx.AsyncClient] = httpx.AsyncClient()

    ################################################################################################################################################################################
    async def gather(self, request_handlers: List[ChatClient]) -> None:

        if len(request_handlers) == 0 or len(self._chat_server_localhost_urls) == 0:
            return

        coros = []
        for idx, handler in enumerate(request_handlers):
            # 循环复用
            endpoint_url = self._chat_server_localhost_urls[
                idx % len(self._chat_server_localhost_urls)
            ]
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

    ################################################################################################################################################################################
    def request(self, request_handlers: List[ChatClient]) -> None:

        if len(request_handlers) == 0 or len(self._chat_server_localhost_urls) == 0:
            return

        for request_handler in request_handlers:
            start_time = time.time()
            request_handler.request(self._chat_server_localhost_urls[0])
            end_time = time.time()
            logger.debug(f"ChatSystem.handle:{end_time - start_time:.2f} seconds")

    ################################################################################################################################################################################
