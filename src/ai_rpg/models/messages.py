"""自定义消息类型"""

from dataclasses import dataclass
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

from pydantic import BaseModel, ConfigDict, Field


############################################################################################################
class BaseMessage(BaseModel):
    """消息基类"""

    model_config = ConfigDict(extra="allow")

    type: str
    content: str = ""
    additional_kwargs: Dict[str, Any] = Field(
        default_factory=dict
    )  # 显式声明字段，避免与 extra="allow" 冲突导致无法访问, LLM 响应的结构化附属数据（目前专用于存 reasoning_content）

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)


############################################################################################################
class SystemMessage(BaseMessage):
    """系统提示消息"""

    type: Literal["system"] = "system"

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)


############################################################################################################
class HumanMessage(BaseMessage):
    """用户消息"""

    type: Literal["human"] = "human"

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)


############################################################################################################
class AIMessage(BaseMessage):
    """AI 回复消息"""

    type: Literal["ai"] = "ai"

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)


############################################################################################################
class ToolMessage(BaseMessage):
    """工具调用结果消息（将工具执行结果回传给 LLM）"""

    type: Literal["tool"] = "tool"
    tool_call_id: str  # 对应 LLM 发出的 ToolCall.id


############################################################################################################
# 显式判别联合：反序列化时强制以 type 字段区分子类，未知 type 值会立即报错
ChatMessage = Annotated[
    Union[SystemMessage, HumanMessage, AIMessage, ToolMessage],
    Field(discriminator="type"),
]

############################################################################################################


def _format_tool_calls(tool_calls: Any) -> str:
    """把 `AIMessage.additional_kwargs['tool_calls']` 渲染为可读多行文本。

    兼容原始 API 格式（dict）与对象形式的 ToolCall；无调用时返回空串。
    """
    if not isinstance(tool_calls, list) or not tool_calls:
        return ""
    lines: List[str] = ["[tool_calls]"]
    for tc in tool_calls:
        if isinstance(tc, dict):
            function = tc.get("function") or {}
            name = function.get("name", "?")
            arguments = function.get("arguments", "")
        else:
            function = getattr(tc, "function", None)
            name = getattr(function, "name", "?")
            arguments = getattr(function, "arguments", "")
        lines.append(f"  ↳ {name}({arguments})")
    return "\n".join(lines)


############################################################################################################
def get_buffer_string(
    messages: Sequence[BaseMessage],
    system_prefix: str = "System",
    human_prefix: str = "Human",
    ai_prefix: str = "AI",
    tool_prefix: str = "Tool",
    render_tool_calls: bool = False,
) -> str:
    """将消息序列转换为单一字符串（用于调试、日志或 prompt 拼接）。

    ``render_tool_calls`` 为 True 时，额外渲染 `AIMessage` 的 tool_calls（默认关闭，
    避免影响存档 buffer / 压缩留痕等既有文本的体量）。
    """

    lines: List[str] = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            role = human_prefix
        elif isinstance(msg, AIMessage):
            role = ai_prefix
        elif isinstance(msg, SystemMessage):
            role = system_prefix
        elif isinstance(msg, ToolMessage):
            role = tool_prefix
        else:
            raise ValueError(f"不支持的消息类型: {type(msg)}")

        content = msg.content

        # 可选：把 AI 消息的 tool_calls 一并渲染出来
        if render_tool_calls and isinstance(msg, AIMessage):
            calls = _format_tool_calls(msg.additional_kwargs.get("tool_calls"))
            if calls:
                content = f"{content}\n{calls}" if content else calls

        # 拼接 role 和 content
        lines.append(f"{role}: {content}")

    # 返回拼接后的字符串
    return "\n".join(lines)


############################################################################################################
# 消息序列查询工具：与 get_buffer_string 同级的纯函数，供任意持有 Sequence[BaseMessage] 的模块复用。
MsgT = TypeVar("MsgT", bound=BaseMessage)


############################################################################################################
@dataclass
class MessageSpan(Generic[MsgT]):
    """一段连续消息在序列中的边界（起终点，闭区间）及其内容。"""

    start_index: int
    end_index: int
    messages: List[MsgT]

    @property
    def start_message(self) -> MsgT:
        return self.messages[0]

    @property
    def end_message(self) -> MsgT:
        return self.messages[-1]

    def __len__(self) -> int:
        return len(self.messages)


############################################################################################################
def find_message(
    messages: Sequence[MsgT],
    predicate: Callable[[MsgT], bool],
    *,
    reverse: bool = False,
) -> Optional[MsgT]:
    """返回首个（``reverse=True`` 时最后一个）满足谓词的消息；无匹配返回 None。"""
    indices = range(len(messages) - 1, -1, -1) if reverse else range(len(messages))
    for i in indices:
        if predicate(messages[i]):
            return messages[i]
    return None


############################################################################################################
def _resolve_span_end(
    messages: Sequence[BaseMessage],
    start_index: int,
    start_attr: str,
    value: Any,
    end_attr: str,
) -> int:
    """从 start_index 起解析区间终点。

    优先匹配 ``getattr(msg, end_attr) == value``；找不到时退化为「下一个带 start_attr
    的消息前一条」，再退化到序列末尾。同属性标记时跳过起点自身，避免自我匹配。
    """
    begin = start_index + 1 if end_attr == start_attr else start_index
    for j in range(begin, len(messages)):
        if getattr(messages[j], end_attr, None) == value:
            return j
    for j in range(start_index + 1, len(messages)):
        if getattr(messages[j], start_attr, None) is not None:
            return j - 1
    return len(messages) - 1


############################################################################################################
def find_marked_span(
    messages: Sequence[MsgT],
    start_attr: str,
    value: Any,
    *,
    end_attr: Optional[str] = None,
) -> Optional[MessageSpan[MsgT]]:
    """按标记属性在消息序列中定位一段区间（起终点，闭区间）。

    - 起点：首个 ``getattr(msg, start_attr, None) == value`` 的消息；
    - 终点：起点之后首个 ``getattr(msg, end_attr, None) == value`` 的消息
      （``end_attr`` 缺省等于 ``start_attr``，即首尾用同一属性标记）；
    - 找不到终点标记时退化为「下一个带 start_attr 的消息前一条」，再退化到序列末尾。

    ``value`` 不得为 None（None 表示「无标记」）；无匹配起点时返回 None。
    """
    if value is None:
        return None
    resolved_end_attr = end_attr if end_attr is not None else start_attr
    for i, msg in enumerate(messages):
        if getattr(msg, start_attr, None) == value:
            end_index = _resolve_span_end(
                messages, i, start_attr, value, resolved_end_attr
            )
            return MessageSpan(
                start_index=i,
                end_index=end_index,
                messages=list(messages[i : end_index + 1]),
            )
    return None


############################################################################################################
def find_marked_spans(
    messages: Sequence[MsgT],
    start_attr: str,
    *,
    end_attr: Optional[str] = None,
) -> List[MessageSpan[MsgT]]:
    """按出现顺序返回序列中所有被 ``start_attr`` 标记的区间。"""
    resolved_end_attr = end_attr if end_attr is not None else start_attr
    spans: List[MessageSpan[MsgT]] = []
    i = 0
    while i < len(messages):
        value = getattr(messages[i], start_attr, None)
        if value is None:
            i += 1
            continue
        end_index = _resolve_span_end(messages, i, start_attr, value, resolved_end_attr)
        spans.append(
            MessageSpan(
                start_index=i,
                end_index=end_index,
                messages=list(messages[i : end_index + 1]),
            )
        )
        i = end_index + 1
    return spans
