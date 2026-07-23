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
from datetime import datetime
from typing import Any, Dict, Final, List, Literal, Optional, Sequence, final
import httpx
import requests
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel

from ..models.messages import (
    HumanMessage,
    AIMessage,
    BaseMessage,
    ToolMessage,
    get_buffer_string,
)
from . import config
from .config import CHAT_DUMP_DIR, MODEL_FLASH

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
    "tool": "tool",
}


############################################################################################################
class ToolFunction(BaseModel):
    """工具函数参数的 JSON Schema 描述（对应 DeepSeek/OpenAI tools[].function）"""

    name: str  # 工具名称，应与业务逻辑函数名一致
    description: str  # 面向 LLM 的工具功能说明
    parameters: Dict[str, Any]  # 参数的 JSON Schema（object 类型）


############################################################################################################
class ToolDefinition(BaseModel):
    """单个工具定义，对应 DeepSeek/OpenAI tools 数组的一个元素"""

    type: Literal["function"] = "function"  # 固定为 "function"
    function: ToolFunction  # 函数描述内容


############################################################################################################
class ToolCall(BaseModel):
    """LLM 返回的单次工具调用指令（finish_reason == \"tool_calls\" 时存在）"""

    class Function(BaseModel):
        name: str  # 被调用的工具名称
        arguments: str  # JSON 序列化的参数字符串

    id: str  # 本次调用的唯一 ID，需在 ToolMessage 中回传
    type: str = "function"  # 固定为 "function"
    function: Function  # 函数调用信息


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
        model: str = MODEL_FLASH,
        thinking: bool = False,
        timeout: Optional[int] = None,
        temperature: Optional[float] = None,
        compressed_prompt: Optional[str] = None,
        tools: Optional[Sequence[ToolDefinition]] = None,
        tool_choice: Optional[Literal["auto", "none", "required"]] = None,
    ) -> None:
        """初始化 DeepSeek 直连客户端

        Args:
            name: 客户端标识名称
            prompt: 发送给 AI 的提示词（完整版，用于推理）；传空字符串表示 continuation 模式（不追加 user 消息）
            context: 历史对话上下文（使用本模块的消息类型）
            model: 使用的模型，默认 _MODEL_FLASH；可选 _MODEL_PRO
            thinking: True 开启思考模式（thinking enabled），默认 False
            timeout: 请求超时（秒），默认 30
            compressed_prompt: 写入对话历史的压缩版提示词；若为 None 则使用 prompt
            tools: 工具定义列表；传入后自动启用 tool calling
            tool_choice: 工具选择策略，默认：有 tools 时为 "required"，否则为 "none"
        """
        assert name != "", "name should not be empty"
        _tools: List[ToolDefinition] = list(tools) if tools else []
        assert (
            prompt != "" or len(_tools) > 0
        ), "prompt should not be empty when no tools are provided"

        self._name: Final[str] = name
        self._prompt: Final[str] = prompt
        self._compressed_prompt: Final[str] = (
            compressed_prompt if compressed_prompt is not None else prompt
        )
        self._context: Sequence[BaseMessage] = context
        self._model: Final[str] = model
        self._thinking: Final[bool] = thinking
        self._timeout: Final[int] = timeout if timeout is not None else 30
        self._tools: Final[List[ToolDefinition]] = _tools
        self._tool_choice: Final[Literal["auto", "none", "required"]] = (
            tool_choice
            if tool_choice is not None
            else ("required" if _tools else "none")
        )

        assert self._timeout > 0, "timeout should be positive"

        if not self._context:
            logger.warning(f"{self._name}: context is empty")

        self._response_ai_message: Optional[AIMessage] = None
        self._prompt_cache_hit_tokens: int = 0
        self._prompt_cache_miss_tokens: int = 0
        self._finish_reason: str = ""
        self._tool_calls: List[ToolCall] = []
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
    @property
    def finish_reason(self) -> str:
        """最近一次响应的 finish_reason；调用 chat() 前为空字符串"""
        return self._finish_reason

    ################################################################################################################################################################################
    @property
    def tool_calls(self) -> List[ToolCall]:
        """最近一次响应中 LLM 发起的 tool 调用列表；无 tool call 时为空列表"""
        return self._tool_calls

    ################################################################################################################################################################################
    def _build_payload(self) -> Dict[str, Any]:
        """将 context + prompt 转换为 DeepSeek API payload"""
        messages: List[Dict[str, Any]] = []
        for msg in self._context:
            if isinstance(msg, ToolMessage):
                # ToolMessage 需要额外携带 tool_call_id 字段
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )
            elif isinstance(msg, AIMessage):
                # AIMessage 含 tool_calls 时需带上 tool_calls 字段，content 可为 null
                raw_tool_calls = msg.additional_kwargs.get("tool_calls")
                if raw_tool_calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": msg.content or None,
                            "tool_calls": raw_tool_calls,
                        }
                    )
                else:
                    messages.append({"role": "assistant", "content": msg.content})
            else:
                role = _ROLE_MAP.get(msg.type, "user")
                content = (
                    msg.content if isinstance(msg.content, str) else str(msg.content)
                )
                messages.append({"role": role, "content": content})

        # prompt 为空字符串时表示 continuation 模式，不追加 user 消息
        if self._prompt != "":
            messages.append({"role": "user", "content": self._prompt})

        payload: Dict[str, Any] = {
            "messages": messages,
            "model": self._model,
            "thinking": {"type": "enabled" if self._thinking else "disabled"},
            "frequency_penalty": 0,
            "max_tokens": 4096,
            "presence_penalty": 0,
            "response_format": {"type": "text"},
            "stop": None,
            "stream": False,
            "stream_options": None,
            "temperature": self._temperature,
            "top_p": 1,
            "tools": [t.model_dump() for t in self._tools] if self._tools else None,
            "tool_choice": self._tool_choice,
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

        choice = choices[0]
        self._finish_reason = choice.get("finish_reason") or ""

        message = choice.get("message", {})
        content: str = message.get("content") or ""
        additional_kwargs: Dict[str, Any] = {}

        reasoning = message.get("reasoning_content")
        if reasoning:
            additional_kwargs["reasoning_content"] = reasoning

        # 解析 LLM 发起的工具调用指令
        raw_tool_calls = message.get("tool_calls")
        if raw_tool_calls:
            additional_kwargs["tool_calls"] = raw_tool_calls
            self._tool_calls = [
                ToolCall(
                    id=tc["id"],
                    type=tc.get("type", "function"),
                    function=ToolCall.Function(
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    ),
                )
                for tc in raw_tool_calls
            ]
        else:
            self._tool_calls = []

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
    async def chat(self) -> None:
        """异步发送聊天请求（直连 DeepSeek 平台）

        Raises:
            httpx.TimeoutException: 请求超时
            httpx.ConnectError: 连接失败
            httpx.RequestError: 其他网络错误
            httpx.HTTPStatusError: HTTP 响应状态码非 200
        """
        logger.debug(f"{self._name} a_request prompt:\n{self._prompt}")
        start_time = time.time()

        try:
            response = await DeepSeekClient.get_async_client().post(
                url=_DEEPSEEK_API_URL,
                headers=self._build_headers(),
                json=self._build_payload(),
                timeout=self._timeout,
            )
        except httpx.TimeoutException as e:
            logger.error(f"{self._name}: async timeout: {type(e).__name__}: {e}")
            raise
        except httpx.ConnectError as e:
            logger.error(
                f"{self._name}: async connection error: {type(e).__name__}: {e}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"{self._name}: async request error: {type(e).__name__}: {e}")
            raise

        elapsed = time.time() - start_time
        logger.debug(f"{self._name} a_request time: {elapsed:.2f}s")

        if response.status_code == 200:

            # 解析响应并填充 response_content 和相关属性
            self._parse_response(response.json())
            logger.info(f"{self._name} response_content:\n{self.response_content}")
            logger.debug(
                f"{self._name} cache: hit={self.prompt_cache_hit_tokens}, miss={self.prompt_cache_miss_tokens}"
            )

            # deepseek-reasoner 模型的思考过程内容通常较长，我们单独记录在 info 级别日志中，方便用户查看但不干扰主要输出
            if self.response_reasoning_content:
                logger.info(
                    f"\n💭 {self._name} 思考过程:\n{self.response_reasoning_content}\n"
                )
                logger.info("=" * 60)

            # 记录完整对话内容以供调试分析
            self._dump_chat()
        else:

            # 记录错误响应信息
            self._handle_error_response(response.status_code, response.text)
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )

    ################################################################################################################################################################################
    def _build_dump_content(self) -> str:
        """将本次对话渲染为纯文本，以分割线分隔各段。"""
        # 拷贝 context，再把本轮 prompt / response 分别补齐为 HumanMessage / AIMessage，
        # 使全部消息（含本轮）统一交给 get_buffer_string 一次性渲染，
        # 避免手工拼接 lines 导致的分隔符/格式不一致问题。
        messages: List[BaseMessage] = list(self._context)
        messages.append(
            HumanMessage(
                content=(
                    self._prompt
                    if self._prompt
                    else "（continuation 模式，无独立 prompt）"
                )
            )
        )
        messages.append(AIMessage(content=self.response_content))

        _SEP = "-" * 86
        content = get_buffer_string(
            messages,
            system_prefix="\n" + _SEP + "\nSystem",
            human_prefix="\n" + _SEP + "\nHuman",
            ai_prefix="\n" + _SEP + "\nAI",
            tool_prefix="\n" + _SEP + "\nTool",
        )

        # Reasoning（可选）
        if self.response_reasoning_content:
            content += "\n" + _SEP + "\n" + self.response_reasoning_content

        return content + "\n"

    ################################################################################################################################################################################
    def _dump_chat(self) -> None:
        """将本次 chat() 完整对话写入 .chat_dumps/ 下的 Markdown 文件。

        文件名格式：{YYYYMMDD_HHMMSS_ffffff}_{name}.md（含微秒防并发冲突）
        写入失败只记录 warning，不向上抛异常。
        """
        if not config.CHAT_DUMP_ENABLED:
            return
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            dump_file = CHAT_DUMP_DIR / f"{timestamp}_{self._name}.txt"
            CHAT_DUMP_DIR.mkdir(parents=True, exist_ok=True)
            dump_file.write_text(self._build_dump_content(), encoding="utf-8")
            logger.debug(f"chat dump saved: {dump_file}")
        except Exception as e:
            logger.warning(
                f"_dump_chat failed for '{self._name}': {type(e).__name__}: {e}"
            )

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
            *[c.chat() for c in clients], return_exceptions=True
        )
        elapsed = time.time() - start_time
        logger.debug(
            f"DeepSeekClient.batch_chat: {len(clients)} clients, {elapsed:.2f}s"
        )

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                name = clients[i].name if i < len(clients) else "unknown"
                logger.error(
                    f"Request failed for '{name}': {type(result).__name__}: {result}"
                )

        failed = sum(1 for r in results if isinstance(r, BaseException))
        if failed:
            logger.warning(f"DeepSeekClient.batch_chat: {failed}/{len(clients)} failed")
        else:
            logger.debug(
                f"DeepSeekClient.batch_chat: all {len(clients)} requests succeeded"
            )

    ################################################################################################################################################################################
