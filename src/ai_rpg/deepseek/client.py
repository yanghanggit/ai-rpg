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

本类是**无状态服务**：请求内容在 `ChatCompletionRequest` 里，结果在 `ChatCompletionResult` 里，
自己只保留 provider 私有事实（模型名 / 上下文长度 / 接口地址 / 鉴权）。
因此同一个实例可以被反复复用、并发调用，不会残留上一轮的响应或错误。
"""

import os
import time
from contextlib import AbstractAsyncContextManager
from typing import (
    Any,
    Callable,
    Dict,
    Final,
    List,
    Optional,
    Protocol,
    TypeAlias,
    final,
)

import httpx
import requests
from dotenv import load_dotenv
from loguru import logger

from ..llm import chat_dump
from ..llm.errors import ChatError, ErrorKind
from ..llm.types import (
    ChatCompletionRequest,
    ChatCompletionResult,
    ToolCall,
    ToolDefinition,
    ToolFunction,
    Usage,
)
from ..models import AIMessage, ToolMessage

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
class HttpResponse(Protocol):
    """`complete()` 需要的最小响应面（便于测试替身，不绑定 httpx.Response）。"""

    @property
    def status_code(self) -> int: ...

    @property
    def text(self) -> str: ...

    def json(self) -> Any: ...


class HttpClient(Protocol):
    """`complete()` 需要的最小 HTTP 面；测试可注入替身，生产用 `httpx.AsyncClient`。"""

    async def post(
        self,
        url: str,
        *,
        headers: Dict[str, str],
        json: Dict[str, Any],
        timeout: float,
    ) -> HttpResponse: ...


# 每次请求取一个 HTTP 客户端（async context manager）；默认 httpx，可注入替身。
HttpClientFactory: TypeAlias = Callable[[], AbstractAsyncContextManager[HttpClient]]


# provider 默认值（请求里没显式给时生效）
_DEFAULT_TIMEOUT_SECONDS: Final[int] = 30
_DEFAULT_TEMPERATURE: Final[float] = 1.0
_DEFAULT_MAX_TOKENS: Final[int] = 16384
_DEFAULT_CONTEXT_WINDOW: Final[int] = 1_000_000

# provider 无关的数据类型在本模块再导出：既有导入点无需改动。
__all__ = [
    "DeepSeekClient",
    "ToolCall",
    "ToolDefinition",
    "ToolFunction",
    "Usage",
]


############################################################################################################
@final
class DeepSeekClient:
    """直连 DeepSeek 平台的 chat completion 服务（实现 `ChatCompletionService`）。

    直接调用 https://api.deepseek.com/chat/completions，
    支持 deepseek-chat 和 deepseek-reasoner 两个模型；`complete()` 的语义就是
    「给定消息历史，请模型补全下一条 assistant 消息」。

    不显式继承协议，靠结构匹配满足；一致性由 tests/unit/test_llm_protocol.py
    的静态断言 + 调用点类型注解共同保证。

    构造函数只留一个测试/传输注入点：``http_client_factory`` 决定每次请求用哪个
    HTTP 客户端（默认 ``httpx.AsyncClient``）。请求内容与响应状态都不在实例上。
    """

    def __init__(
        self, http_client_factory: HttpClientFactory = httpx.AsyncClient
    ) -> None:
        self._http_client_factory: Final[HttpClientFactory] = http_client_factory

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
    @classmethod
    def context_window(cls, model: Optional[str]) -> int:
        """给定模型的上下文长度上限（输入 + 输出 token 总数）；未知模型按默认值。"""
        if model is None:
            return cls.CONTEXT_WINDOW_TOKENS.get(
                cls.MODEL_FLASH, _DEFAULT_CONTEXT_WINDOW
            )
        return cls.CONTEXT_WINDOW_TOKENS.get(model, _DEFAULT_CONTEXT_WINDOW)

    ################################################################################################################################################################################
    @classmethod
    def _build_payload(cls, request: ChatCompletionRequest) -> Dict[str, Any]:
        """将 request 转换为 DeepSeek API payload（provider 私有细节集中在这里）。"""
        messages: List[Dict[str, Any]] = []
        for msg in request.messages:
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
                # 走到这里只可能是 SystemMessage / HumanMessage（AI / Tool 已在上分支处理）
                role = _ROLE_MAP.get(msg.type, "user")
                messages.append({"role": role, "content": msg.content})

        # input_message 为空字符串时表示 continuation 模式，不追加 user 消息
        if request.input_message != "":
            messages.append({"role": "user", "content": request.input_message})

        # tools 缺省时 tool_choice 退化为 "none"；有 tools 但未指定则要求必须调用
        tool_choice = request.tool_choice
        if tool_choice is None:
            tool_choice = "required" if request.tools else "none"

        payload: Dict[str, Any] = {
            "messages": messages,
            "model": request.model if request.model is not None else cls.MODEL_FLASH,
            "thinking": {
                "type": "enabled" if request.thinking else "disabled",
            },
            "max_tokens": (
                request.max_tokens
                if request.max_tokens is not None
                else _DEFAULT_MAX_TOKENS
            ),
            "response_format": {"type": "text"},
            "stream": False,
            "temperature": (
                request.temperature
                if request.temperature is not None
                else _DEFAULT_TEMPERATURE
            ),
            "tools": (
                [t.model_dump() for t in request.tools] if request.tools else None
            ),
            "tool_choice": tool_choice,
        }
        # reasoning_effort 仅当显式指定时传入
        if request.reasoning_effort is not None:
            payload["reasoning_effort"] = request.reasoning_effort
        return payload

    ################################################################################################################################################################################
    @classmethod
    def _parse_response(
        cls,
        request: ChatCompletionRequest,
        data: Dict[str, Any],
        elapsed_seconds: float,
    ) -> ChatCompletionResult:
        """解析 DeepSeek API 响应，构造 `ChatCompletionResult`。"""
        choices = data.get("choices", [])
        if not choices:
            logger.warning(f"{request.label}: empty choices in response")
            return ChatCompletionResult(
                request=request, elapsed_seconds=elapsed_seconds
            )

        choice = choices[0]

        # 解析 finish_reason
        finish_reason: str = choice.get("finish_reason") or ""

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
        tool_calls: List[ToolCall] = []
        if raw_tool_calls:
            # 将原始 tool_calls 保留在 additional_kwargs 里（回传给下一轮时需要原样带上）
            additional_kwargs["tool_calls"] = raw_tool_calls

            tool_calls = [
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

        # 解析 token 用量统计（response 顶层字段，与 choices 平级）
        usage_data = data.get("usage")
        assert usage_data is not None, "usage_data should not be None"
        completion_tokens_details = usage_data.get("completion_tokens_details") or {}
        usage = Usage(
            prompt_tokens=usage_data["prompt_tokens"],
            completion_tokens=usage_data["completion_tokens"],
            total_tokens=usage_data["total_tokens"],
            prompt_cache_hit_tokens=usage_data.get("prompt_cache_hit_tokens", 0),
            prompt_cache_miss_tokens=usage_data.get("prompt_cache_miss_tokens", 0),
            reasoning_tokens=completion_tokens_details.get("reasoning_tokens", 0),
        )

        # 上下文占比：AgentMemory 的同步逻辑从 AI 消息的额外属性上读，故仍打在消息上
        # （该值需要随记忆一起持久化，放在消息上是最省事的载体）。
        context_usage_ratio = usage.total_tokens / cls.context_window(request.model)

        ai_message = AIMessage(
            content=content,
            additional_kwargs=additional_kwargs,
            context_usage_ratio=context_usage_ratio,
        )

        return ChatCompletionResult(
            request=request,
            ai_message=ai_message,
            finish_reason=finish_reason,
            tool_calls=tuple(tool_calls),
            usage=usage,
            elapsed_seconds=elapsed_seconds,
        )

    ################################################################################################################################################################################
    @staticmethod
    def _handle_error_response(
        label: str, status_code: int, response_text: str
    ) -> None:
        """根据 DeepSeek 文档记录对应状态码的错误信息"""
        match status_code:
            case 400:
                logger.error(
                    f"{label}: 请求格式错误 (400) — 请检查请求体: {response_text}"
                )
            case 401:
                logger.error(
                    f"{label}: 认证失败 (401) — API key 错误，请检查 DEEPSEEK_API_KEY"
                )
            case 402:
                logger.error(f"{label}: 余额不足 (402) — 请前往 DeepSeek 平台充值")
            case 422:
                logger.error(
                    f"{label}: 参数错误 (422) — 请检查请求参数: {response_text}"
                )
            case 429:
                logger.warning(f"{label}: 请求速率达到上限 (429) — 请稍后重试")
            case 500:
                logger.error(
                    f"{label}: 服务器内部故障 (500) — 请稍后重试，如持续出现请联系 DeepSeek"
                )
            case 503:
                logger.warning(f"{label}: 服务器繁忙 (503) — 请稍后重试")
            case _:
                logger.error(f"{label}: 请求失败 ({status_code}): {response_text}")

    ################################################################################################################################################################################
    @staticmethod
    def _failed(
        request: ChatCompletionRequest,
        kind: ErrorKind,
        message: str,
        elapsed_seconds: float,
        status_code: Optional[int] = None,
    ) -> ChatCompletionResult:
        """构造失败结果：预期内失败不抛异常，只填 `error`。"""
        return ChatCompletionResult(
            request=request,
            error=ChatError(request.label, message, kind=kind, status_code=status_code),
            elapsed_seconds=elapsed_seconds,
        )

    ################################################################################################################################################################################
    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        """执行一次 chat completion 请求（POST /chat/completions）。

        预期内的失败（超时 / 连接错误 / 非 200）**不抛异常**，而是填进
        ``ChatCompletionResult.error``：这样批量场景不必再靠 ``client.error`` 旁路对账，
        也不会被 ``asyncio.gather`` 把异常吞成返回值。
        """
        logger.debug(
            f"{request.label} a_request input_message:\n{request.input_message}"
        )
        start_time = time.time()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {DeepSeekClient.get_api_key()}",
        }
        timeout = (
            request.timeout if request.timeout is not None else _DEFAULT_TIMEOUT_SECONDS
        )

        try:
            async with self._http_client_factory() as http_client:
                response = await http_client.post(
                    url=_DEEPSEEK_API_URL,
                    headers=headers,
                    json=self._build_payload(request),
                    timeout=timeout,
                )
        except httpx.TimeoutException as e:
            logger.error(f"{request.label}: async timeout: {type(e).__name__}: {e}")
            return self._failed(
                request,
                "timeout",
                f"async timeout: {type(e).__name__}: {e}",
                time.time() - start_time,
            )
        except httpx.ConnectError as e:
            logger.error(
                f"{request.label}: async connection error: {type(e).__name__}: {e}"
            )
            return self._failed(
                request,
                "connection",
                f"async connection error: {type(e).__name__}: {e}",
                time.time() - start_time,
            )
        except httpx.RequestError as e:
            logger.error(
                f"{request.label}: async request error: {type(e).__name__}: {e}"
            )
            return self._failed(
                request,
                "connection",
                f"async request error: {type(e).__name__}: {e}",
                time.time() - start_time,
            )

        elapsed = time.time() - start_time
        logger.debug(f"{request.label} a_request time: {elapsed:.2f}s")

        if response.status_code != 200:
            # 记录错误响应信息
            self._handle_error_response(
                request.label, response.status_code, response.text
            )
            return self._failed(
                request,
                "api",
                f"HTTP {response.status_code}",
                elapsed,
                response.status_code,
            )

        # 解析响应
        completion = self._parse_response(request, response.json(), elapsed)

        # 直接打印完整的 response
        logger.debug(f"{request.label} full response:\n{response.json()}")

        # 仅打印 response_content 和 reasoning_content，方便用户查看
        logger.info(f"{request.label} completion content:\n{completion.content}")

        # deepseek-reasoner 模型的思考过程内容通常较长，我们单独记录在 info 级别日志中，方便用户查看但不干扰主要输出
        if completion.reasoning_content:
            logger.info(
                f"\n💭 {request.label} 思考过程:\n{completion.reasoning_content}\n"
            )
            logger.info("=" * 60)

        # 记录完整对话内容以供调试分析（request.dump=False / 进程级关闭时内部直接返回）
        chat_dump.dump_chat(request, completion)

        return completion


############################################################################################################
# 全项目共用的默认 DeepSeek 服务实例：无状态，可被任意系统/任务反复复用。
# 放在这里（而不是 `__init__`）是为了让 agent_loop / batch 绑定层与业务侧共用同一个。
DEEPSEEK_SERVICE: Final[DeepSeekClient] = DeepSeekClient()
