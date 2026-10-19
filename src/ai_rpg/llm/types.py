"""与具体 provider 无关的 chat completion 数据类型。

命名对齐 OpenAI / DeepSeek 的 ``POST /chat/completions``：一次请求 = 给定消息
历史 + 本轮用户输入，让模型**补全**下一条 assistant 消息；返回的就是那条补全结果。
它描述的是一次「补全」，不是「开启一个聊天会话」，所以类型名都带 ``ChatCompletion``。

这些结构是 OpenAI 兼容的（DeepSeek 直接沿用），因此不属于 `ai_rpg.deepseek`：
任何一家 OpenAI 兼容服务、以及未来的本地模型网关都能复用同一套定义。

依赖方向：`ai_rpg.llm` 是被依赖方，本模块**不得** import `ai_rpg.deepseek`。
"""

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel

from ..models import AIMessage, ChatMessage
from .errors import ChatError

############################################################################################################
# tool_choice 取值（OpenAI 兼容）
ToolChoice = Literal["auto", "none", "required"]

# reasoning_effort 取值（DeepSeek 思考模式档位；其他 provider 可自行映射或忽略）
ReasoningEffort = Literal["low", "high", "max"]


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
@dataclass(frozen=True)
class ChatCompletionRequest:
    """一次 chat completion 请求（不可变值对象）。

    对应 ``POST /chat/completions`` 的请求体语义：``messages``（历史）+
    ``input_message``（本轮用户输入）交给模型，要求它补全下一条 assistant 消息。

    把「问 LLM 什么」从执行者身上剥离出来：同一个 service 可以连续/并发处理任意
    多个 request，不必为每次请求新建 client，也不会出现「同一个对象上还留着上一轮
    响应」的问题。
    """

    label: str
    input_message: str
    messages: Sequence[ChatMessage]  # 只读历史；调用方后续 append 不影响已发出的请求
    model: Optional[str] = None
    thinking: bool = False
    timeout: Optional[int] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Sequence[ToolDefinition] = ()
    tool_choice: Optional[ToolChoice] = None
    reasoning_effort: Optional[ReasoningEffort] = None
    dump: bool = True

    def __post_init__(self) -> None:
        assert self.label != "", "label should not be empty"
        assert (
            self.input_message != "" or len(self.tools) > 0
        ), "input_message should not be empty when no tools are provided"
        if self.timeout is not None:
            assert self.timeout > 0, "timeout should be positive"


############################################################################################################
@dataclass(frozen=True)
class ChatCompletionResult:
    """一次 chat completion 的结果（不可变值对象）。

    ``ai_message`` 就是模型补全出来的那条 assistant 消息（含 reasoning_content /
    tool_calls 等附属数据），``finish_reason`` / ``tool_calls`` / ``usage`` 都是
    ``/chat/completions`` 响应里的同名字段。

    ``error`` 是唯一的失败通道：预期内的通讯失败（超时/连接/非 200）不抛异常，
    而是落在 ``error`` 上，因此批量场景不需要再靠 ``client.error`` 旁路对账，
    也不会被 ``asyncio.gather`` 把异常吞成返回值。真正的 bug / 取消仍会抛出。

    ``request`` 一并带回：调用方（dump、记忆留痕、日志）常需要「问了什么」。
    """

    request: ChatCompletionRequest
    ai_message: Optional[AIMessage] = None
    finish_reason: str = ""
    tool_calls: Tuple[ToolCall, ...] = ()
    usage: Optional[Usage] = None
    error: Optional[ChatError] = None
    elapsed_seconds: float = 0.0

    @property
    def label(self) -> str:
        """请求标签，等价于 ``request.label``（批量场景下定位用）。"""
        return self.request.label

    @property
    def ok(self) -> bool:
        """是否成功拿到响应。"""
        return self.error is None

    @property
    def content(self) -> str:
        """响应文本；无响应时为空串。"""
        if self.ai_message is None:
            return ""
        return self.ai_message.content

    @property
    def reasoning_content(self) -> str:
        """推理过程内容（thinking mode 才有）；无则为空串。"""
        if self.ai_message is None:
            return ""
        value = self.ai_message.additional_kwargs.get("reasoning_content")
        if value is None:
            return ""
        return value if isinstance(value, str) else str(value)


__all__ = [
    "ChatCompletionRequest",
    "ChatCompletionResult",
    "ReasoningEffort",
    "ToolCall",
    "ToolChoice",
    "ToolDefinition",
    "ToolFunction",
    "Usage",
]
