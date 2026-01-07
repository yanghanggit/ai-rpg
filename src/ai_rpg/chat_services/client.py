import asyncio
from typing import Final, List, Optional, final
import httpx
import requests
import traceback
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger
from .protocol import (
    ChatRequest,
    ChatResponse,
)
import time
from ..configuration.server import ServerConfiguration
from dataclasses import dataclass


################################################################################################################################################################################
@dataclass
class DeepSeekUrlConfig:
    base_url: str
    chat_url: str
    reasoner_url: str


################################################################################################################################################################################
@final
class ChatClient:

    # Static AsyncClient instance for all ChatClient instances
    _async_client: httpx.AsyncClient = httpx.AsyncClient()

    # DeepSeek API URL configuration
    _deepseek_url_config: Optional[DeepSeekUrlConfig] = None

    @classmethod
    def initialize_url_config(cls, server_settings: ServerConfiguration) -> None:
        """Initialize the URL configurations from ServerSettings."""

        cls._deepseek_url_config = DeepSeekUrlConfig(
            base_url=f"http://localhost:{server_settings.deepseek_chat_server_port}/",
            chat_url=f"http://localhost:{server_settings.deepseek_chat_server_port}/api/chat/v1/",
            reasoner_url=f"http://localhost:{server_settings.deepseek_chat_server_port}/api/chat/reasoner/v1/",
        )

        logger.info(
            f"ChatClient initialized with DeepSeek URLs: {cls._deepseek_url_config}"
        )

    ################################################################################################################################################################################
    @classmethod
    def get_async_client(cls) -> httpx.AsyncClient:
        """Get the shared AsyncClient instance."""
        return cls._async_client

    ################################################################################################################################################################################
    @classmethod
    async def close_async_client(cls) -> None:
        """Close the shared AsyncClient instance."""
        if cls._async_client is not None:
            await cls._async_client.aclose()
            cls._async_client = httpx.AsyncClient()

    ################################################################################################################################################################################
    def __init__(
        self,
        name: str,
        prompt: str,
        context: List[SystemMessage | HumanMessage | AIMessage],
        url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:

        self._name = name
        assert self._name != "", "agent_name should not be empty"

        self._prompt: Final[str] = prompt
        assert self._prompt != "", "prompt should not be empty"

        self._context: List[SystemMessage | HumanMessage | AIMessage] = context
        if len(self._context) == 0:
            logger.warning(f"{self._name}: context is empty")

        self._chat_response: ChatResponse = ChatResponse()

        assert (
            self._deepseek_url_config is not None
        ), "DeepSeek URL config is not initialized"

        self._url: Optional[str] = (
            url if url is not None else self._deepseek_url_config.chat_url
        )

        self._timeout: Final[int] = timeout if timeout is not None else 30
        assert self._timeout > 0, "timeout should be positive"

        for message in self._context:
            assert isinstance(message, (HumanMessage, AIMessage, SystemMessage))

        self._cache_response_ai_messages: Optional[List[AIMessage]] = None

    ################################################################################################################################################################################
    @property
    def name(self) -> str:
        return self._name

    ################################################################################################################################################################################
    @property
    def prompt(self) -> str:
        return self._prompt

    ################################################################################################################################################################################
    @property
    def url(self) -> str:
        if self._url is None:
            return ""
        return self._url

    ################################################################################################################################################################################
    @property
    def response_content(self) -> str:
        if len(self.response_ai_messages) == 0:
            return ""

        last_message = self.response_ai_messages[-1]

        # 处理 content 的不同类型
        content = last_message.content

        # 如果 content 已经是字符串，直接返回
        if isinstance(content, str):
            return content

        # 如果 content 是列表，需要处理列表中的元素
        if isinstance(content, list):
            # 将列表中的每个元素转换为字符串并连接
            content_parts = []
            for item in content:
                if isinstance(item, str):
                    content_parts.append(item)
                elif isinstance(item, dict):
                    # 对于字典类型，转换为 JSON 字符串或简单的字符串表示
                    content_parts.append(str(item))
                else:
                    # 其他类型，直接转换为字符串
                    content_parts.append(str(item))
            return "\n".join(content_parts)

        # 兜底情况：直接转换为字符串
        return str(content)

    ################################################################################################################################################################################
    @property
    def response_ai_messages(self) -> List[AIMessage]:

        if self._cache_response_ai_messages is not None:
            return self._cache_response_ai_messages

        self._cache_response_ai_messages = []
        for message in self._chat_response.messages:
            if message.type == "ai":
                if isinstance(message, AIMessage):
                    self._cache_response_ai_messages.append(message)
                else:
                    self._cache_response_ai_messages.append(
                        AIMessage.model_validate(message.model_dump())
                    )

        # 再检查一次！！！
        for check_message in self._cache_response_ai_messages:
            assert isinstance(check_message, AIMessage)

        return self._cache_response_ai_messages

    ################################################################################################################################################################################
    def request_post(self) -> None:

        try:

            logger.debug(f"{self._name} request prompt:\n{self._prompt}")

            start_time = time.time()

            response = requests.post(
                url=self.url,
                json=ChatRequest(
                    message=HumanMessage(content=self._prompt),
                    context=self._context,
                ).model_dump(),
                timeout=self._timeout,
            )

            end_time = time.time()
            logger.debug(
                f"{self._name} request time:{end_time - start_time:.2f} seconds"
            )

            if response.status_code == 200:
                self._chat_response = ChatResponse.model_validate(response.json())
                # logger.info(
                #     f"{self._name} request-response:\n{self._chat_response.model_dump_json()}"
                # )
                logger.info(f"{self._name} response_content:\n{self.response_content}")

                # 🧠 显示思考过程 (reasoning_content 在 additional_kwargs 中)
                if self.response_ai_messages:
                    latest_response = self.response_ai_messages[-1]
                    reasoning_content = latest_response.additional_kwargs.get(
                        "reasoning_content"
                    )
                    if reasoning_content:
                        logger.info(
                            f"\n💭 {self._name} 思考过程:\n{reasoning_content}\n"
                        )
                        logger.info("=" * 60)
            else:
                logger.error(
                    f"request-response Error: {response.status_code}, {response.text}"
                )

        except requests.exceptions.Timeout as e:
            logger.error(
                f"{self._name}: request timeout error: {type(e).__name__}: {e}"
            )
        except requests.exceptions.ConnectionError as e:
            logger.error(f"{self._name}: connection error: {type(e).__name__}: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"{self._name}: request error: {type(e).__name__}: {e}")
        except Exception as e:
            logger.error(f"{self._name}: unexpected error: {type(e).__name__}: {e}")
            logger.debug(f"{self._name}: full traceback:\n{traceback.format_exc()}")

    ################################################################################################################################################################################
    async def a_request_post(self) -> None:

        try:

            logger.debug(f"{self._name} a_request prompt:\n{self._prompt}")

            start_time = time.time()

            response = await ChatClient.get_async_client().post(
                url=self.url,
                json=ChatRequest(
                    message=HumanMessage(content=self._prompt),
                    context=self._context,
                ).model_dump(),
                timeout=self._timeout,
            )

            end_time = time.time()
            logger.debug(
                f"{self._name} a_request time:{end_time - start_time:.2f} seconds"
            )

            if response.status_code == 200:
                self._chat_response = ChatResponse.model_validate(response.json())
                # logger.info(
                #     f"{self._name} a_request-response:\n{self._chat_response.model_dump_json()}"
                # )
                logger.info(f"{self._name} response_content:\n{self.response_content}")

                # 🧠 显示思考过程 (reasoning_content 在 additional_kwargs 中)
                if self.response_ai_messages:
                    latest_response = self.response_ai_messages[-1]
                    reasoning_content = latest_response.additional_kwargs.get(
                        "reasoning_content"
                    )
                    if reasoning_content:
                        logger.info(
                            f"\n💭 {self._name} 思考过程:\n{reasoning_content}\n"
                        )
                        logger.info("=" * 60)
            else:
                logger.error(
                    f"a_request-response Error: {response.status_code}, {response.text}"
                )

            # buffer_str = get_buffer_string(self._context + self.response_ai_messages)
            # logger.debug(f"{self._name} full chat buffer:\n{buffer_str}")

        except httpx.TimeoutException as e:
            logger.error(f"{self._name}: async timeout error: {type(e).__name__}: {e}")
        except httpx.ConnectError as e:
            logger.error(
                f"{self._name}: async connection error: {type(e).__name__}: {e}"
            )
        except httpx.RequestError as e:
            logger.error(f"{self._name}: async request error: {type(e).__name__}: {e}")
        except Exception as e:
            logger.error(
                f"{self._name}: unexpected async error: {type(e).__name__}: {e}"
            )
            logger.debug(f"{self._name}: full traceback:\n{traceback.format_exc()}")

    ################################################################################################################################################################################

    @staticmethod
    async def gather_request_post(clients: List["ChatClient"]) -> None:
        """使用ChatClient列表进行异步批量请求"""
        if not clients:
            return

        coros = []
        for client in clients:
            coros.append(client.a_request_post())

        # 允许异常捕获，不中断其他请求
        start_time = time.time()
        batch_results = await asyncio.gather(*coros, return_exceptions=True)
        end_time = time.time()
        logger.debug(
            f"ChatClient.gather_request_post: {len(clients)} clients, {end_time - start_time:.2f} seconds"
        )

        # 记录失败请求
        failed_count = 0
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                client_name = clients[i].name if i < len(clients) else "unknown"
                logger.error(
                    f"Request failed for client '{client_name}': {type(result).__name__}: {result}"
                )
                failed_count += 1

        if failed_count > 0:
            logger.warning(
                f"ChatClient.gather_request_post: {failed_count}/{len(clients)} requests failed"
            )
        else:
            logger.debug(
                f"ChatClient.gather_request_post: All {len(clients)} requests completed successfully"
            )

    ################################################################################################################################################################################

    @staticmethod
    async def health_check() -> None:
        """检查所有客户端的健康状态"""
        if ChatClient._deepseek_url_config is None:
            logger.warning("ChatClient URL configurations are not initialized")
            return

        base_urls = [
            ChatClient._deepseek_url_config.base_url,
        ]

        for base_url in base_urls:
            try:
                response = await ChatClient.get_async_client().get(f"{base_url}")
                response.raise_for_status()
                # 打印response
                logger.debug(f"Health check response from {base_url}: {response.text}")
                logger.debug(f"Health check passed: {base_url}")
            except Exception as e:
                logger.error(f"Health check failed: {base_url}, error: {e}")

    ################################################################################################################################################################################
