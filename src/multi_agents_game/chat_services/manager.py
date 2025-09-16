import asyncio
from enum import StrEnum, unique
import time
from typing import Final, List, NamedTuple, Optional, final
import httpx
from loguru import logger
from .client import ChatClient


###################################################################################################################################################################
@final
class ChatClientEndpoint(NamedTuple):
    chat_client: ChatClient
    url: str


###################################################################################################################################################################
@final
@unique
class ChatApiEndpointOptions(StrEnum):
    AZURE_OPENAI_BASE = "azure_openai_base"
    AZURE_OPENAI_CHAT = "azure_openai_chat"
    DEEPSEEK_BASE = "deepseek_base"
    DEEPSEEK_CHAT = "deepseek_chat"
    DEEPSEEK_RAG_CHAT = "deepseek_rag_chat"
    DEEPSEEK_UNDEFINED_CHAT = "deepseek_undefined_chat"
    DEEPSEEK_MCP_CHAT = "deepseek_mcp_chat"


@final
class ChatClientManager:

    ################################################################################################################################################################################
    def __init__(
        self,
        azure_openai_base_localhost_urls: List[str],
        azure_openai_chat_localhost_urls: List[str],
        deepseek_base_localhost_urls: List[str],
        deepseek_chat_localhost_urls: List[str],
        deepseek_rag_chat_localhost_urls: List[str],
        deepseek_undefined_chat_localhost_urls: List[str],
        deepseek_mcp_chat_localhost_urls: List[str],
    ) -> None:

        assert len(azure_openai_base_localhost_urls) > 0
        self._azure_openai_base_localhost_urls: Final[List[str]] = (
            azure_openai_base_localhost_urls
        )
        logger.debug(
            f"Azure OpenAI Base URLs: {self._azure_openai_base_localhost_urls}"
        )

        # 运行的服务器
        assert len(azure_openai_chat_localhost_urls) > 0
        self._azure_openai_chat_localhost_urls: Final[List[str]] = (
            azure_openai_chat_localhost_urls
        )
        logger.debug(
            f"Azure OpenAI Chat URLs: {self._azure_openai_chat_localhost_urls}"
        )

        assert len(deepseek_base_localhost_urls) > 0
        self._deepseek_base_localhost_urls: Final[List[str]] = (
            deepseek_base_localhost_urls
        )
        logger.debug(f"DeepSeek Base URLs: {self._deepseek_base_localhost_urls}")

        assert len(deepseek_chat_localhost_urls) > 0
        self._deepseek_chat_localhost_urls: Final[List[str]] = (
            deepseek_chat_localhost_urls
        )
        logger.debug(f"DeepSeek Chat URLs: {self._deepseek_chat_localhost_urls}")

        # 临时添加的
        self._deepseek_rag_chat_localhost_urls: Final[List[str]] = (
            deepseek_rag_chat_localhost_urls
        )
        logger.debug(f"DeepSeek RAG URLs: {self._deepseek_rag_chat_localhost_urls}")
        self._deepseek_undefined_chat_localhost_urls: Final[List[str]] = (
            deepseek_undefined_chat_localhost_urls
        )
        logger.debug(
            f"DeepSeek Undefined URLs: {self._deepseek_undefined_chat_localhost_urls}"
        )
        self._deepseek_mcp_chat_localhost_urls: Final[List[str]] = (
            deepseek_mcp_chat_localhost_urls
        )
        logger.debug(f"DeepSeekMCP URLs: {self._deepseek_mcp_chat_localhost_urls}")

        # 异步请求客户端
        self._async_client: Final[httpx.AsyncClient] = httpx.AsyncClient()

    ################################################################################################################################################################################
    def get_urls_by_option(
        self, options: Optional[ChatApiEndpointOptions]
    ) -> List[str]:
        # return self._deepseek_chat_localhost_urls

        if options is None or options == ChatApiEndpointOptions.AZURE_OPENAI_CHAT:
            return self._azure_openai_chat_localhost_urls
        elif options == ChatApiEndpointOptions.AZURE_OPENAI_BASE:
            return self._azure_openai_base_localhost_urls
        elif options == ChatApiEndpointOptions.DEEPSEEK_BASE:
            return self._deepseek_base_localhost_urls
        elif options == ChatApiEndpointOptions.DEEPSEEK_CHAT:
            return self._deepseek_chat_localhost_urls
        elif options == ChatApiEndpointOptions.DEEPSEEK_RAG_CHAT:
            return self._deepseek_rag_chat_localhost_urls
        elif options == ChatApiEndpointOptions.DEEPSEEK_UNDEFINED_CHAT:
            return self._deepseek_undefined_chat_localhost_urls
        elif options == ChatApiEndpointOptions.DEEPSEEK_MCP_CHAT:
            return self._deepseek_mcp_chat_localhost_urls

        # 兜底情况，如果有新的未处理的选项
        return self._azure_openai_chat_localhost_urls

    ################################################################################################################################################################################
    def create_chat_client_endpoints(
        self, request_handlers: List[ChatClient], urls: List[str]
    ) -> List[ChatClientEndpoint]:
        """
        创建聊天客户端端点列表，处理request_handlers与urls的循环复用逻辑

        Args:
            request_handlers: 聊天客户端列表
            urls: URL列表

        Returns:
            ChatClientEndpoint列表，每个端点包含一个ChatClient和对应的URL
        """
        if not request_handlers or not urls:
            return []

        client_endpoints = []
        for idx, handler in enumerate(request_handlers):
            # 循环复用URLs
            url = urls[idx % len(urls)]
            client_endpoints.append(ChatClientEndpoint(chat_client=handler, url=url))

        return client_endpoints

    ################################################################################################################################################################################
    async def gather(
        self,
        request_handlers: List[ChatClient],
        options: Optional[ChatApiEndpointOptions] = None,
    ) -> None:
        client_endpoints = self.create_chat_client_endpoints(
            request_handlers, self.get_urls_by_option(options)
        )
        return await self._gather_with_endpoints(client_endpoints)

    ################################################################################################################################################################################
    async def _gather_with_endpoints(
        self, client_endpoints: List[ChatClientEndpoint]
    ) -> None:
        """使用ChatClientEndpoint列表进行异步批量请求"""
        if not client_endpoints:
            return

        coros = []
        for endpoint in client_endpoints:
            coros.append(
                endpoint.chat_client.a_request(self._async_client, endpoint.url)
            )

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
    def request(
        self,
        request_handlers: List[ChatClient],
        options: Optional[ChatApiEndpointOptions] = None,
    ) -> None:
        client_endpoints = self.create_chat_client_endpoints(
            request_handlers, self.get_urls_by_option(options)
        )
        return self._request_with_endpoints(client_endpoints)

    ################################################################################################################################################################################
    def _request_with_endpoints(
        self, client_endpoints: List[ChatClientEndpoint]
    ) -> None:
        """使用ChatClientEndpoint列表进行同步批量请求"""
        if not client_endpoints:
            return

        for endpoint in client_endpoints:
            start_time = time.time()
            endpoint.chat_client.request(endpoint.url)
            end_time = time.time()
            logger.debug(f"ChatSystem.handle:{end_time - start_time:.2f} seconds")

    ################################################################################################################################################################################
    async def health_check(
        self, options: Optional[ChatApiEndpointOptions] = None
    ) -> None:
        """检查所有客户端的健康状态"""
        base_urls = self.get_urls_by_option(options)
        if not base_urls:
            return

        for base_url in base_urls:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{base_url}")
                    response.raise_for_status()
                    # 打印response
                    logger.info(
                        f"Health check response from {base_url}: {response.text}"
                    )
                    logger.info(f"Health check passed: {base_url}")
            except Exception as e:
                logger.error(f"Health check failed: {base_url}, error: {e}")

    ################################################################################################################################################################################
