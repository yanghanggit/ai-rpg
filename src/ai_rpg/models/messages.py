"""自定义消息类型"""

from typing import Annotated, Any, Dict, List, Literal, Sequence, Union

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
