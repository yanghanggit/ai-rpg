"""DeepSeek 直连客户端

直接调用 DeepSeek 平台 REST API.

temperature 参数默认为 1.0。
我们建议您根据如下表格，按使用场景设置 temperature。
场景	温度
代码生成/数学解题 0.0
数据抽取/分析	1.0
通用对话	1.3
翻译	1.3
创意类写作/诗歌创作	1.5

"""

import os
import time
from typing import (
    Any,
    Dict,
    Final,
    List,
    Literal,
    NoReturn,
    Optional,
    Sequence,
    final,
)

import httpx
import requests
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel

from ..models.messages import AIMessage, BaseMessage, ToolMessage
from . import chat_dump
from .errors import DeepSeekError, ErrorKind

load_dotenv()

############################################################################################################
_DEEPSEEK_API_URL: Final[str] = "https://api.deepseek.com/chat/completions"
_DEEPSEEK_MODELS_URL: Final[str] = "https://api.deepseek.com/models"
_DEEPSEEK_BALANCE_URL: Final[str] = "https://api.deepseek.com/user/balance"

# DeepSeek 消息 role 映射：system/human/ai/tool
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
class Usage(BaseModel):
    """响应中的 token 用量统计（对应 DeepSeek/OpenAI usage 字段）"""

    prompt_tokens: int  # 本次请求上下文（输入）消耗的 token 数
    completion_tokens: int  # 本次生成（输出）消耗的 token 数
    total_tokens: int  # 输入 + 输出的 token 总数
    prompt_cache_hit_tokens: int  # 命中 KVCache 的输入 token 数
    prompt_cache_miss_tokens: int  # 未命中 KVCache 的输入 token 数
    reasoning_tokens: int = 0  # 思考过程消耗的 token 数；非思考模式响应中不返回该字段


############################################################################################################
@final
class DeepSeekClient:
    """直连 DeepSeek 平台的聊天客户端

    直接调用 https://api.deepseek.com/chat/completions，
    支持 deepseek-chat 和 deepseek-reasoner 两个模型。
    公共接口与 ChatClient 保持一致。
    """

    # DeepSeek 模型名称
    MODEL_FLASH: Final[str] = (
        "deepseek-flash"  # DeepSeek-V4.1-Flash，支持视觉（旧名 deepseek-v4-flash 已下线）
    )
    MODEL_PRO: Final[str] = (
        "deepseek-v4-pro"  # V4 Pro（已下线；2026-09-14 起请求路由到 V4.1 Flash，按 Flash 计费）
    )

    # 各模型的上下文长度上限（输入 + 输出 token 总数），取值见 DeepSeek 定价文档
    CONTEXT_WINDOW_TOKENS: Final[Dict[str, int]] = {
        MODEL_FLASH: 1_000_000,
        MODEL_PRO: 1_000_000,
    }

    ################################################################################################################################################################################
    @classmethod
    def get_api_key(cls) -> str:
        """每次从环境变量读取 API Key"""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set")
        return api_key

    ################################################################################################################################################################################
    @classmethod
    def list_models(cls) -> List[str]:
        """列出 DeepSeek 平台上当前可用的模型 ID"""
        try:
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {cls.get_api_key()}",
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
        """查询账户余额"""
        try:
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {cls.get_api_key()}",
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
    def __init__(
        self,
        name: str,
        prompt: str,
        messages: Sequence[BaseMessage],
        model: str = MODEL_FLASH,
        thinking: bool = False,
        timeout: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[Sequence[ToolDefinition]] = None,
        tool_choice: Optional[Literal["auto", "none", "required"]] = None,
        reasoning_effort: Optional[Literal["low", "high", "max"]] = None,
    ) -> None:
        """初始化 DeepSeek 直连客户端"""
        assert name != "", "name should not be empty"
        _tools: List[ToolDefinition] = list(tools) if tools else []
        assert (
            prompt != "" or len(_tools) > 0
        ), "prompt should not be empty when no tools are provided"

        self._name: Final[str] = name
        self._prompt: Final[str] = prompt
        self._messages: Final[Sequence[BaseMessage]] = messages
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

        if not self._messages:
            logger.warning(f"{self._name}: messages is empty")

        self._temperature: Final[float] = (
            temperature if temperature is not None else 1.0
        )
        self._max_tokens: Final[int] = max_tokens if max_tokens is not None else 16384
        self._reasoning_effort: Final[Optional[Literal["low", "high", "max"]]] = (
            reasoning_effort
        )

        # 输出
        self._response_ai_message: Optional[AIMessage] = None
        self._finish_reason: str = ""
        self._tool_calls: List[ToolCall] = []
        self._usage: Optional[Usage] = None
        self._error: Optional[DeepSeekError] = None

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
    def error(self) -> Optional[DeepSeekError]:
        """最近一次 chat() 的失败原因；成功或尚未调用时为 None。"""
        return self._error

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
        """获取推理思考过程内容（thinking mode 开启时有效）"""
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
    @property
    def usage(self) -> Optional[Usage]:
        """最近一次响应的 token 用量统计；调用 chat() 前为 None"""
        return self._usage

    ################################################################################################################################################################################
    @property
    def context_window(self) -> int:
        """当前模型的上下文长度上限（输入 + 输出 token 总数）"""
        return DeepSeekClient.CONTEXT_WINDOW_TOKENS.get(self._model, 1_000_000)

    ################################################################################################################################################################################
    @property
    def context_usage_ratio(self) -> float:
        """最近一次响应 total_tokens 占模型上下文长度的比例；调用 chat() 前为 0.0"""
        if self._usage is None:
            return 0.0
        return self._usage.total_tokens / self.context_window

    ################################################################################################################################################################################
    def _build_payload(self) -> Dict[str, Any]:
        """将 messages + prompt 转换为 DeepSeek API payload"""
        messages: List[Dict[str, Any]] = []
        for msg in self._messages:
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
            "max_tokens": self._max_tokens,
            "response_format": {"type": "text"},
            "stream": False,
            "temperature": self._temperature,
            "tools": [t.model_dump() for t in self._tools] if self._tools else None,
            "tool_choice": self._tool_choice,
        }
        # reasoning_effort 仅当显式指定时传入
        if self._reasoning_effort is not None:
            payload["reasoning_effort"] = self._reasoning_effort
        return payload

    ################################################################################################################################################################################
    def _parse_response(self, data: Dict[str, Any]) -> None:
        """解析 DeepSeek API 响应并填充 _response_ai_message"""
        choices = data.get("choices", [])
        if not choices:
            logger.warning(f"{self._name}: empty choices in response")
            return

        choice = choices[0]

        # 解析 finish_reason
        self._finish_reason = choice.get("finish_reason") or ""

        message = choice.get("message", {})
        content: str = message.get("content") or ""

        # 解析 reasoning_content 和 tool_calls，存入 additional_kwargs
        additional_kwargs: Dict[str, Any] = {}

        reasoning = message.get("reasoning_content")
        if reasoning:
            # deepseek-reasoner 模型的思考过程内容通常较长，我们单独记录在 additional_kwargs 中，方便用户查看但不干扰主要输出
            additional_kwargs["reasoning_content"] = reasoning

        # 解析 LLM 发起的工具调用指令
        raw_tool_calls = message.get("tool_calls")
        if raw_tool_calls:

            # 将原始 tool_calls 转换为 ToolCall 对象列表
            additional_kwargs["tool_calls"] = raw_tool_calls

            # 将原始 tool_calls 转换为 ToolCall 对象列表
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

        # 解析 token 用量统计（response 顶层字段，与 choices 平级）
        usage_data = data.get("usage")
        assert usage_data is not None, "usage_data should not be None"
        completion_tokens_details = usage_data.get("completion_tokens_details") or {}
        self._usage = Usage(
            prompt_tokens=usage_data["prompt_tokens"],
            completion_tokens=usage_data["completion_tokens"],
            total_tokens=usage_data["total_tokens"],
            prompt_cache_hit_tokens=usage_data.get("prompt_cache_hit_tokens", 0),
            prompt_cache_miss_tokens=usage_data.get("prompt_cache_miss_tokens", 0),
            reasoning_tokens=completion_tokens_details.get("reasoning_tokens", 0),
        )

        # 构建 AIMessage 对象，包含 content、additional_kwargs 与上下文占比
        self._response_ai_message = AIMessage(
            content=content,
            additional_kwargs=additional_kwargs,
            context_usage_ratio=self.context_usage_ratio,
        )

    ################################################################################################################################################################################
    def _handle_error_response(self, status_code: int, response_text: str) -> None:
        """根据 DeepSeek 文档记录对应状态码的错误信息"""
        # 以上代码用match来重构
        match status_code:
            case 400:
                logger.error(
                    f"{self._name}: 请求格式错误 (400) — 请检查请求体: {response_text}"
                )
            case 401:
                logger.error(
                    f"{self._name}: 认证失败 (401) — API key 错误，请检查 DEEPSEEK_API_KEY"
                )
            case 402:
                logger.error(f"{self._name}: 余额不足 (402) — 请前往 DeepSeek 平台充值")
            case 422:
                logger.error(
                    f"{self._name}: 参数错误 (422) — 请检查请求参数: {response_text}"
                )
            case 429:
                logger.warning(f"{self._name}: 请求速率达到上限 (429) — 请稍后重试")
            case 500:
                logger.error(
                    f"{self._name}: 服务器内部故障 (500) — 请稍后重试，如持续出现请联系 DeepSeek"
                )
            case 503:
                logger.warning(f"{self._name}: 服务器繁忙 (503) — 请稍后重试")
            case _:
                logger.error(f"{self._name}: 请求失败 ({status_code}): {response_text}")

    ################################################################################################################################################################################
    async def chat(self, client: Optional[httpx.AsyncClient] = None) -> None:
        """异步发送聊天请求（直连 DeepSeek 平台）。

        单独调用时不传 client，内部临时创建；
        batch_chat 时传入共享 client 以复用连接池。

        每次调用开头重置响应态，保证同一 client 上一次的响应不会掩盖本次结果
        （供业务层在失败后自行重试时使用）。失败时记录到 self._error 并抛出
        DeepSeekError。
        """
        # 重置上一次的响应态与错误记录。
        self._response_ai_message = None
        self._finish_reason = ""
        self._tool_calls = []
        self._usage = None
        self._error = None

        logger.debug(f"{self._name} a_request prompt:\n{self._prompt}")
        start_time = time.time()

        def _fail(
            kind: ErrorKind, message: str, status_code: Optional[int] = None
        ) -> NoReturn:
            """记录并抛出统一错误：先落到 self._error，再抛出 DeepSeekError。"""
            self._error = DeepSeekError(
                self._name, message, kind=kind, status_code=status_code
            )
            raise self._error

        async def _do_post(http_client: httpx.AsyncClient) -> httpx.Response:

            # 构建请求头部信息。
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {DeepSeekClient.get_api_key()}",
            }

            # 发送 POST 请求到 DeepSeek API。
            return await http_client.post(
                url=_DEEPSEEK_API_URL,
                headers=headers,
                json=self._build_payload(),
                timeout=self._timeout,
            )

        try:

            # 使用传入的 client 发送请求，如果没有传入则创建临时 client。
            if client is not None:
                response = await _do_post(client)
            else:
                async with httpx.AsyncClient() as tmp_client:

                    # 创建临时 client 并发送请求。
                    response = await _do_post(tmp_client)

        except httpx.TimeoutException as e:

            # 处理请求超时异常。
            logger.error(f"{self._name}: async timeout: {type(e).__name__}: {e}")
            _fail("timeout", f"async timeout: {type(e).__name__}: {e}")

        except httpx.ConnectError as e:
            # 处理请求连接错误异常。
            logger.error(
                f"{self._name}: async connection error: {type(e).__name__}: {e}"
            )
            _fail("connection", f"async connection error: {type(e).__name__}: {e}")
        except httpx.RequestError as e:
            # 处理请求错误异常。
            logger.error(f"{self._name}: async request error: {type(e).__name__}: {e}")
            _fail("connection", f"async request error: {type(e).__name__}: {e}")

        elapsed = time.time() - start_time
        logger.debug(f"{self._name} a_request time: {elapsed:.2f}s")

        if response.status_code == 200:

            # 解析响应并填充 response_content 和相关属性
            self._parse_response(response.json())

            # 直接打印完整的 response
            logger.debug(f"{self._name} full response:\n{response.json()}")

            # 仅打印 response_content 和 reasoning_content，方便用户查看
            logger.info(f"{self._name} response_content:\n{self.response_content}")

            # deepseek-reasoner 模型的思考过程内容通常较长，我们单独记录在 info 级别日志中，方便用户查看但不干扰主要输出
            if self.response_reasoning_content:
                logger.info(
                    f"\n💭 {self._name} 思考过程:\n{self.response_reasoning_content}\n"
                )
                logger.info("=" * 60)

            # 记录完整对话内容以供调试分析
            if chat_dump.chat_dump_enabled:
                chat_dump.dump_chat(self)

        else:

            # 记录错误响应信息
            self._handle_error_response(response.status_code, response.text)

            # 记录并抛出统一错误：非 200 视为 api 类失败，retryable 由状态码判定。
            _fail("api", f"HTTP {response.status_code}", response.status_code)
