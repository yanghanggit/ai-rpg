import asyncio
import time
from typing import Final, List, final
import httpx
from loguru import logger
from .client import ChatClient


@final
class ChatClientManager:

    ################################################################################################################################################################################
    def __init__(
        self,
        azure_openai_chat_server_localhost_urls: List[str],
        deepseek_chat_server_localhost_urls: List[str],
    ) -> None:

        # 运行的服务器
        assert len(azure_openai_chat_server_localhost_urls) > 0
        self._azure_openai_chat_server_localhost_urls: Final[List[str]] = (
            azure_openai_chat_server_localhost_urls
        )

        self._deepseek_chat_server_localhost_urls: Final[List[str]] = (
            deepseek_chat_server_localhost_urls
        )

        # 当前服务器索引，用于轮询
        self._current_server_index: int = 0

        # 异步请求客户端
        self._async_client: Final[httpx.AsyncClient] = httpx.AsyncClient()

    ################################################################################################################################################################################
    @property
    def current_chat_server_localhost_urls(self) -> List[str]:
        return self._azure_openai_chat_server_localhost_urls

    ################################################################################################################################################################################
    async def gather(self, request_handlers: List[ChatClient]) -> None:

        if (
            len(request_handlers) == 0
            or len(self.current_chat_server_localhost_urls) == 0
        ):
            return

        coros = []
        for idx, handler in enumerate(request_handlers):
            # 循环复用
            endpoint_url = self.current_chat_server_localhost_urls[
                idx % len(self.current_chat_server_localhost_urls)
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

        if (
            len(request_handlers) == 0
            or len(self.current_chat_server_localhost_urls) == 0
        ):
            return

        for request_handler in request_handlers:
            start_time = time.time()

            # 使用当前索引获取服务器URL
            current_url = self.current_chat_server_localhost_urls[
                self._current_server_index
            ]
            request_handler.request(current_url)

            # 移动到下一个服务器，循环轮询
            self._current_server_index = (self._current_server_index + 1) % len(
                self.current_chat_server_localhost_urls
            )

            end_time = time.time()
            logger.debug(f"ChatSystem.handle:{end_time - start_time:.2f} seconds")

    ################################################################################################################################################################################
