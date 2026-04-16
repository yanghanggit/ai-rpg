"""DeepSeek 直连客户端（无 langchain/langgraph 依赖）

直接调用 DeepSeek 平台 REST API，不经过本地 deepseek_chat_server。
公共接口与 ChatClient 保持一致，context 类型改用本模块的自定义消息类型。

temperature 参数默认为 1.0。
我们建议您根据如下表格，按使用场景设置 temperature。
场景	温度
代码生成/数学解题 0.0
数据抽取/分析	1.0
通用对话	1.3
翻译	1.3
创意类写作/诗歌创作	1.5
"""

import asyncio
import os
import time
import traceback
from typing import Any, Dict, Final, List, Optional, Sequence, final
import httpx
import requests
from dotenv import load_dotenv
from loguru import logger

from ..models.messages import AIMessage, BaseMessage

load_dotenv()

############################################################################################################
_DEEPSEEK_API_URL: Final[str] = "https://api.deepseek.com/chat/completions"

# DeepSeek 消息 role 映射
_ROLE_MAP: Final[Dict[str, str]] = {
    "system": "system",
    "human": "user",
    "ai": "assistant",
}


############################################################################################################
@final
class DeepSeekClient:
    """直连 DeepSeek 平台的聊天客户端（无 langchain/langgraph 依赖）

    直接调用 https://api.deepseek.com/chat/completions，
    支持 deepseek-chat 和 deepseek-reasoner 两个模型。
    公共接口与 ChatClient 保持一致。
    """

    _async_client: httpx.AsyncClient = httpx.AsyncClient()

    ################################################################################################################################################################################
    @classmethod
    def _get_api_key(cls) -> str:
        """每次从环境变量读取 API Key

        Raises:
            ValueError: 当 DEEPSEEK_API_KEY 未设置时
        """
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set")
        return api_key

    ################################################################################################################################################################################
    @classmethod
    def setup(cls) -> None:
        """校验 API Key 是否已配置（启动时快速失败）

        Raises:
            ValueError: 当 DEEPSEEK_API_KEY 未设置时
        """
        cls._get_api_key()  # 仅校验，不存储
        logger.info(f"DeepSeekClient initialized, endpoint: {_DEEPSEEK_API_URL}")

    ################################################################################################################################################################################
    @classmethod
    def get_async_client(cls) -> httpx.AsyncClient:
        """获取共享的异步 HTTP 客户端"""
        return cls._async_client

    ################################################################################################################################################################################
    @classmethod
    async def close_async_client(cls) -> None:
        """关闭并重置异步 HTTP 客户端"""
        await cls._async_client.aclose()
        cls._async_client = httpx.AsyncClient()

    ################################################################################################################################################################################
    def __init__(
        self,
        name: str,
        prompt: str,
        context: Sequence[BaseMessage],
        use_reasoner: bool = False,
        timeout: Optional[int] = None,
    ) -> None:
        """初始化 DeepSeek 直连客户端

        Args:
            name: 客户端标识名称
            prompt: 发送给 AI 的提示词
            context: 历史对话上下文（使用本模块的消息类型）
            use_reasoner: True 使用 deepseek-reasoner（思考模式），默认 False 使用 deepseek-chat
            timeout: 请求超时（秒），默认 30
        """
        assert name != "", "name should not be empty"
        assert prompt != "", "prompt should not be empty"

        self._name: Final[str] = name
        self._prompt: Final[str] = prompt
        self._context: Sequence[BaseMessage] = context
        self._use_reasoner: Final[bool] = use_reasoner
        self._timeout: Final[int] = timeout if timeout is not None else 30

        assert self._timeout > 0, "timeout should be positive"

        if not self._context:
            logger.warning(f"{self._name}: context is empty")

        self._response_ai_message: Optional[AIMessage] = None

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
    def response_ai_message(self) -> Optional[AIMessage]:
        """获取 AI 回复消息"""
        return self._response_ai_message

    ################################################################################################################################################################################
    @property
    def response_content(self) -> str:
        """获取 AI 回复的文本内容"""
        if self._response_ai_message is None:
            return ""
        return self._response_ai_message.content

    ################################################################################################################################################################################
    @property
    def response_reasoning_content(self) -> str:
        """获取推理思考过程内容（仅 deepseek-reasoner 有效）"""
        if self._response_ai_message is None:
            return ""
        val = self._response_ai_message.additional_kwargs.get("reasoning_content")
        if val is None:
            return ""
        return val if isinstance(val, str) else str(val)

    ################################################################################################################################################################################
    def _build_payload(self) -> Dict[str, Any]:
        """将 context + prompt 转换为 DeepSeek API payload"""
        messages: List[Dict[str, str]] = []
        for msg in self._context:
            role = _ROLE_MAP.get(msg.type, "user")
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": self._prompt})

        model = "deepseek-reasoner" if self._use_reasoner else "deepseek-chat"
        payload: Dict[str, Any] = {
            "messages": messages,
            "model": model,
            "thinking": {"type": "enabled" if self._use_reasoner else "disabled"},
            "frequency_penalty": 0,
            "max_tokens": 4096,
            "presence_penalty": 0,
            "response_format": {"type": "text"},
            "stop": None,
            "stream": False,
            "stream_options": None,
            "temperature": 1,
            "top_p": 1,
            "tools": None,
            "tool_choice": "none",
            "logprobs": False,
            "top_logprobs": None,
        }
        return payload

    ################################################################################################################################################################################
    def _parse_response(self, data: Dict[str, Any]) -> None:
        """解析 DeepSeek API 响应并填充 _response_ai_message"""
        choices = data.get("choices", [])
        if not choices:
            logger.warning(f"{self._name}: empty choices in response")
            return

        message = choices[0].get("message", {})
        content: str = message.get("content") or ""
        additional_kwargs: Dict[str, Any] = {}

        reasoning = message.get("reasoning_content")
        if reasoning:
            additional_kwargs["reasoning_content"] = reasoning

        self._response_ai_message = AIMessage(
            content=content,
            additional_kwargs=additional_kwargs,
        )

    ################################################################################################################################################################################
    def _build_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {DeepSeekClient._get_api_key()}",
        }

    ################################################################################################################################################################################
    def chat(self) -> None:
        """同步发送聊天请求（直连 DeepSeek 平台）"""
        try:
            logger.debug(f"{self._name} request prompt:\n{self._prompt}")
            start_time = time.time()

            response = requests.post(
                url=_DEEPSEEK_API_URL,
                headers=self._build_headers(),
                json=self._build_payload(),
                timeout=self._timeout,
            )

            elapsed = time.time() - start_time
            logger.debug(f"{self._name} request time: {elapsed:.2f}s")

            if response.status_code == 200:
                self._parse_response(response.json())
                logger.info(f"{self._name} response_content:\n{self.response_content}")
                if self.response_reasoning_content:
                    logger.info(
                        f"\n💭 {self._name} 思考过程:\n{self.response_reasoning_content}\n"
                    )
                    logger.info("=" * 60)
            else:
                logger.error(
                    f"{self._name} response Error: {response.status_code}, {response.text}"
                )

        except requests.exceptions.Timeout as e:
            logger.error(f"{self._name}: request timeout: {type(e).__name__}: {e}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"{self._name}: connection error: {type(e).__name__}: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"{self._name}: request error: {type(e).__name__}: {e}")
        except Exception as e:
            logger.error(f"{self._name}: unexpected error: {type(e).__name__}: {e}")
            logger.debug(f"{self._name}: traceback:\n{traceback.format_exc()}")

    ################################################################################################################################################################################
    async def async_chat(self) -> None:
        """异步发送聊天请求（直连 DeepSeek 平台）"""
        try:
            logger.debug(f"{self._name} a_request prompt:\n{self._prompt}")
            start_time = time.time()

            response = await DeepSeekClient.get_async_client().post(
                url=_DEEPSEEK_API_URL,
                headers=self._build_headers(),
                json=self._build_payload(),
                timeout=self._timeout,
            )

            elapsed = time.time() - start_time
            logger.debug(f"{self._name} a_request time: {elapsed:.2f}s")

            if response.status_code == 200:
                self._parse_response(response.json())
                logger.info(f"{self._name} response_content:\n{self.response_content}")
                if self.response_reasoning_content:
                    logger.info(
                        f"\n💭 {self._name} 思考过程:\n{self.response_reasoning_content}\n"
                    )
                    logger.info("=" * 60)
            else:
                logger.error(
                    f"{self._name} a_response Error: {response.status_code}, {response.text}"
                )

        except httpx.TimeoutException as e:
            logger.error(f"{self._name}: async timeout: {type(e).__name__}: {e}")
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
            logger.debug(f"{self._name}: traceback:\n{traceback.format_exc()}")

    ################################################################################################################################################################################
    @staticmethod
    async def batch_chat(clients: List["DeepSeekClient"]) -> None:
        """批量并发发送聊天请求

        Args:
            clients: 客户端列表
        """
        if not clients:
            return

        start_time = time.time()
        results = await asyncio.gather(
            *[c.async_chat() for c in clients], return_exceptions=True
        )
        elapsed = time.time() - start_time
        logger.debug(
            f"DeepSeekClient.batch_chat: {len(clients)} clients, {elapsed:.2f}s"
        )

        failed = sum(1 for r in results if isinstance(r, Exception))
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                name = clients[i].name if i < len(clients) else "unknown"
                logger.error(
                    f"Request failed for '{name}': {type(result).__name__}: {result}"
                )

        if failed:
            logger.warning(f"DeepSeekClient.batch_chat: {failed}/{len(clients)} failed")
        else:
            logger.debug(
                f"DeepSeekClient.batch_chat: all {len(clients)} requests succeeded"
            )

    ################################################################################################################################################################################
