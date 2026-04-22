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
_DEEPSEEK_MODELS_URL: Final[str] = "https://api.deepseek.com/models"
_DEEPSEEK_BALANCE_URL: Final[str] = "https://api.deepseek.com/user/balance"

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
    def list_models(cls) -> List[str]:
        """列出 DeepSeek 平台上当前可用的模型 ID

        Returns:
            模型 ID 列表；请求失败时返回空列表
        """
        try:
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {cls._get_api_key()}",
            }
            response = requests.get(
                url=_DEEPSEEK_MODELS_URL,
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                data: Dict[str, Any] = response.json()
                model_ids: List[str] = [
                    m["id"] for m in data.get("data", []) if "id" in m
                ]
                logger.info(f"DeepSeekClient.list_models: {model_ids}")
                return model_ids
            else:
                logger.error(
                    f"DeepSeekClient.list_models failed ({response.status_code}): {response.text}"
                )
                return []
        except requests.exceptions.RequestException as e:
            logger.error(
                f"DeepSeekClient.list_models request error: {type(e).__name__}: {e}"
            )
            return []

    ################################################################################################################################################################################
    @classmethod
    def get_balance(cls) -> Dict[str, Any]:
        """查询账户余额

        Returns:
            余额信息字典，包含 is_available 和 balance_infos 字段；
            请求失败时返回空字典
        """
        try:
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {cls._get_api_key()}",
            }
            response = requests.get(
                url=_DEEPSEEK_BALANCE_URL,
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                data: Dict[str, Any] = response.json()
                logger.info(f"DeepSeekClient.get_balance: {data}")
                return data
            else:
                logger.error(
                    f"DeepSeekClient.get_balance failed ({response.status_code}): {response.text}"
                )
                return {}
        except requests.exceptions.RequestException as e:
            logger.error(
                f"DeepSeekClient.get_balance request error: {type(e).__name__}: {e}"
            )
            return {}

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
        temperature: Optional[float] = None,
        compressed_prompt: Optional[str] = None,
    ) -> None:
        """初始化 DeepSeek 直连客户端

        Args:
            name: 客户端标识名称
            prompt: 发送给 AI 的提示词（完整版，用于推理）
            context: 历史对话上下文（使用本模块的消息类型）
            use_reasoner: True 使用 deepseek-reasoner（思考模式），默认 False 使用 deepseek-chat
            timeout: 请求超时（秒），默认 30
            compressed_prompt: 写入对话历史的压缩版提示词；若为 None 则使用 prompt
        """
        assert name != "", "name should not be empty"
        assert prompt != "", "prompt should not be empty"

        self._name: Final[str] = name
        self._prompt: Final[str] = prompt
        self._compressed_prompt: Final[str] = (
            compressed_prompt if compressed_prompt is not None else prompt
        )
        self._context: Sequence[BaseMessage] = context
        self._use_reasoner: Final[bool] = use_reasoner
        self._timeout: Final[int] = timeout if timeout is not None else 30

        assert self._timeout > 0, "timeout should be positive"

        if not self._context:
            logger.warning(f"{self._name}: context is empty")

        self._response_ai_message: Optional[AIMessage] = None
        self._prompt_cache_hit_tokens: int = 0
        self._prompt_cache_miss_tokens: int = 0
        self._temperature: Final[float] = (
            temperature if temperature is not None else 1.0
        )

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
    def compressed_prompt(self) -> str:
        """写入对话历史的压缩版提示词"""
        return self._compressed_prompt

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
    def prompt_cache_hit_tokens(self) -> int:
        """本次请求缓存命中的 token 数（计费价格更低）"""
        return self._prompt_cache_hit_tokens

    ################################################################################################################################################################################
    @property
    def prompt_cache_miss_tokens(self) -> int:
        """本次请求缓存未命中的 token 数"""
        return self._prompt_cache_miss_tokens

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
            "temperature": self._temperature,
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

        usage: Dict[str, Any] = data.get("usage", {})
        self._prompt_cache_hit_tokens = int(usage.get("prompt_cache_hit_tokens", 0))
        self._prompt_cache_miss_tokens = int(usage.get("prompt_cache_miss_tokens", 0))

    ################################################################################################################################################################################
    def _handle_error_response(self, status_code: int, response_text: str) -> None:
        """根据 DeepSeek 文档记录对应状态码的错误信息

        Args:
            status_code: HTTP 响应状态码
            response_text: 响应正文（用于 400/422 的调试信息）
        """
        if status_code == 400:
            logger.error(
                f"{self._name}: 请求格式错误 (400) — 请检查请求体: {response_text}"
            )
        elif status_code == 401:
            logger.error(
                f"{self._name}: 认证失败 (401) — API key 错误，请检查 DEEPSEEK_API_KEY"
            )
        elif status_code == 402:
            logger.error(f"{self._name}: 余额不足 (402) — 请前往 DeepSeek 平台充值")
        elif status_code == 422:
            logger.error(
                f"{self._name}: 参数错误 (422) — 请检查请求参数: {response_text}"
            )
        elif status_code == 429:
            logger.warning(f"{self._name}: 请求速率达到上限 (429) — 请稍后重试")
        elif status_code == 500:
            logger.error(
                f"{self._name}: 服务器内部故障 (500) — 请稍后重试，如持续出现请联系 DeepSeek"
            )
        elif status_code == 503:
            logger.warning(f"{self._name}: 服务器繁忙 (503) — 请稍后重试")
        else:
            logger.error(f"{self._name}: 请求失败 ({status_code}): {response_text}")

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
                logger.debug(
                    f"{self._name} cache: hit={self.prompt_cache_hit_tokens}, miss={self.prompt_cache_miss_tokens}"
                )
                if self.response_reasoning_content:
                    logger.info(
                        f"\n💭 {self._name} 思考过程:\n{self.response_reasoning_content}\n"
                    )
                    logger.info("=" * 60)
            else:
                self._handle_error_response(response.status_code, response.text)

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
                logger.debug(
                    f"{self._name} cache: hit={self.prompt_cache_hit_tokens}, miss={self.prompt_cache_miss_tokens}"
                )
                if self.response_reasoning_content:
                    logger.info(
                        f"\n💭 {self._name} 思考过程:\n{self.response_reasoning_content}\n"
                    )
                    logger.info("=" * 60)
            else:
                self._handle_error_response(response.status_code, response.text)

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
