"""
ChatClient - DeepSeek聊天服务客户端

本模块提供了与DeepSeek聊天服务交互的客户端实现，支持同步和异步HTTP请求。

主要功能：
- 支持标准聊天模型（chat）和推理模型（reasoner）
- 提供同步（request_post）和异步（a_request_post）请求方式
- 批量异步请求支持（gather_request_post）
- 自动提取和显示推理思考过程（reasoning_content）
- 连接池管理和健康检查

核心类：
- DeepSeekUrlConfig: URL配置数据类
- ChatClient: 聊天客户端主类，支持多种请求模式

使用示例：
    # 初始化URL配置
    ChatClient.initialize_url_config(server_configuration)

    # 创建客户端（默认使用chat模型）
    client = ChatClient(
        name="test_agent",
        prompt="你好，请介绍一下自己",
        context=[]
    )
    client.request_post()

    # 使用推理模型
    reasoner_client = ChatClient(
        name="reasoner_agent",
        prompt="解释量子纠缠",
        context=[],
        url=ChatClient._deepseek_url_config.reasoner_url
    )
    await reasoner_client.a_request_post()
"""

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
    """
    DeepSeek服务URL配置

    Attributes:
        base_url: 基础URL，用于健康检查
        chat_url: 标准聊天模型端点URL
        reasoner_url: 推理模型端点URL
    """

    base_url: str
    chat_url: str
    reasoner_url: str


################################################################################################################################################################################
@final
class ChatClient:
    """
    DeepSeek聊天服务客户端

    提供与DeepSeek聊天服务交互的完整功能，支持同步和异步请求，
    自动管理连接池和会话状态。

    类属性：
        _async_client: 共享的异步HTTP客户端实例
        _deepseek_url_config: DeepSeek服务URL配置

    实例属性：
        name: 客户端名称/代理名称
        prompt: 发送给AI的提示词
        url: 请求端点URL
        response_content: AI回复的文本内容
        response_reasoning_content: AI的推理思考过程
        response_ai_messages: AI回复的所有消息

    使用流程：
        1. 调用 initialize_url_config() 初始化URL配置
        2. 创建 ChatClient 实例
        3. 调用 request_post() 或 a_request_post() 发起请求
        4. 通过属性获取回复内容
    """

    # Static AsyncClient instance for all ChatClient instances
    _async_client: httpx.AsyncClient = httpx.AsyncClient()

    # DeepSeek API URL configuration
    _deepseek_url_config: Optional[DeepSeekUrlConfig] = None

    @classmethod
    def initialize_url_config(cls, server_settings: ServerConfiguration) -> None:
        """
        初始化DeepSeek服务URL配置

        必须在创建任何ChatClient实例之前调用此方法。
        配置包括基础URL、标准聊天端点和推理模型端点。

        Args:
            server_settings: 服务器配置对象，包含DeepSeek服务端口

        Raises:
            AssertionError: 如果在未初始化URL配置的情况下创建ChatClient实例

        Example:
            >>> from ai_rpg.configuration import server_configuration
            >>> ChatClient.initialize_url_config(server_configuration)
        """

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
        """
        获取共享的异步HTTP客户端实例

        所有ChatClient实例共享同一个AsyncClient，实现连接池管理。

        Returns:
            httpx.AsyncClient: 共享的异步客户端实例
        """
        return cls._async_client

    ################################################################################################################################################################################
    @classmethod
    async def close_async_client(cls) -> None:
        """
        关闭共享的异步HTTP客户端并创建新实例

        用于清理连接池资源，并重新初始化一个新的客户端。
        通常在应用关闭或重启时调用。
        """
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
        """
        初始化ChatClient实例

        Args:
            name: 客户端名称/代理名称，用于日志记录，不能为空
            prompt: 发送给AI的提示词/问题，不能为空
            context: 历史对话上下文，包含系统消息、用户消息和AI消息
            url: 自定义请求端点URL，默认使用chat_url。
                 要使用推理模型，传入ChatClient._deepseek_url_config.reasoner_url
            timeout: HTTP请求超时时间（秒），默认30秒

        Raises:
            AssertionError: 当name或prompt为空，或URL配置未初始化时

        Example:
            >>> client = ChatClient(
            ...     name="test_agent",
            ...     prompt="你好",
            ...     context=[],
            ...     timeout=60
            ... )
        """

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
        """获取客户端名称"""
        return self._name

    ################################################################################################################################################################################
    @property
    def prompt(self) -> str:
        """获取发送给AI的提示词"""
        return self._prompt

    ################################################################################################################################################################################
    @property
    def url(self) -> str:
        """获取请求端点URL"""
        if self._url is None:
            return ""
        return self._url

    ################################################################################################################################################################################
    @property
    def response_content(self) -> str:
        """
        获取AI回复的文本内容

        从最后一条AI消息中提取content字段。
        自动处理字符串、列表、字典等不同类型的内容。

        Returns:
            str: AI回复的文本内容，如果没有回复则返回空字符串
        """
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
    def response_reasoning_content(self) -> str:
        """
        获取推理思考过程内容

        从最后一条AI消息的 additional_kwargs 中提取 reasoning_content。
        如果没有推理内容，返回空字符串。

        Returns:
            str: 推理思考过程的文本内容
        """
        if len(self.response_ai_messages) == 0:
            return ""

        latest_response = self.response_ai_messages[-1]
        reasoning_content = latest_response.additional_kwargs.get("reasoning_content")

        if reasoning_content is None:
            return ""

        # 如果 reasoning_content 已经是字符串，直接返回
        if isinstance(reasoning_content, str):
            return reasoning_content

        # 兜底情况：转换为字符串
        return str(reasoning_content)

    ################################################################################################################################################################################
    @property
    def response_ai_messages(self) -> List[AIMessage]:
        """
        获取AI回复的所有消息

        从响应中提取所有AI类型的消息，并缓存结果。
        确保所有消息都是AIMessage类型。

        Returns:
            List[AIMessage]: AI消息列表
        """

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
        """
        发起同步HTTP POST请求到DeepSeek服务

        使用requests库发起阻塞式请求，适合在同步代码中使用。
        自动记录请求耗时、响应内容和推理思考过程（如有）。

        异常处理：
            - Timeout: 请求超时
            - ConnectionError: 连接错误
            - RequestException: 其他请求错误
            - Exception: 未预期的错误

        所有异常都会被捕获并记录，不会中断程序执行。

        Example:
            >>> client = ChatClient(name="agent", prompt="hello", context=[])
            >>> client.request_post()
            >>> print(client.response_content)
        """

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
                if self.response_reasoning_content:
                    logger.info(
                        f"\n💭 {self._name} 思考过程:\n{self.response_reasoning_content}\n"
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
        """
        发起异步HTTP POST请求到DeepSeek服务

        使用httpx库发起非阻塞式请求，适合在异步代码中使用。
        使用共享的AsyncClient实现连接池管理，提高性能。
        自动记录请求耗时、响应内容和推理思考过程（如有）。

        异常处理：
            - TimeoutException: 异步请求超时
            - ConnectError: 异步连接错误
            - RequestError: 其他异步请求错误
            - Exception: 未预期的错误

        所有异常都会被捕获并记录，不会中断程序执行。

        Example:
            >>> client = ChatClient(name="agent", prompt="hello", context=[])
            >>> await client.a_request_post()
            >>> print(client.response_content)
        """

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
                if self.response_reasoning_content:
                    logger.info(
                        f"\n💭 {self._name} 思考过程:\n{self.response_reasoning_content}\n"
                    )
                    logger.info("=" * 60)
            else:
                logger.error(
                    f"a_request-response Error: {response.status_code}, {response.text}"
                )

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
        """
        批量异步发起多个ChatClient请求

        并行执行多个客户端的请求，大幅提高批量请求效率。
        使用asyncio.gather实现并发，单个请求失败不会影响其他请求。

        Args:
            clients: ChatClient实例列表，每个实例已配置好提示词和上下文

        返回后：
            - 所有客户端的response_content属性已更新
            - 失败的请求会记录到日志
            - 记录总耗时和失败数量

        Example:
            >>> clients = [
            ...     ChatClient(name="agent1", prompt="question1", context=[]),
            ...     ChatClient(name="agent2", prompt="question2", context=[]),
            ... ]
            >>> await ChatClient.gather_request_post(clients)
            >>> for client in clients:
            ...     print(f"{client.name}: {client.response_content}")
        """
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
        """
        检查DeepSeek服务的健康状态

        向配置的基础URL发起GET请求，验证服务是否可用。
        通常在应用启动时或定期检查时调用。

        检查结果会记录到日志，不会抛出异常。

        Example:
            >>> await ChatClient.health_check()
        """
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
