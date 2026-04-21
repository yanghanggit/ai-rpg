"""自定义消息类型（仿 langchain 风格，无 langchain 依赖）

提供与 langchain_core.messages 接口兼容的消息类型：
- BaseMessage
- SystemMessage
- HumanMessage
- AIMessage
"""

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


############################################################################################################
class SystemMessage(BaseMessage):
    """系统提示消息"""

    type: Literal["system"] = "system"


############################################################################################################
class HumanMessage(BaseMessage):
    """用户消息"""

    type: Literal["human"] = "human"


############################################################################################################
class AIMessage(BaseMessage):
    """AI 回复消息"""

    type: Literal["ai"] = "ai"


############################################################################################################
# 显式判别联合：反序列化时强制以 type 字段区分子类，未知 type 值会立即报错
ContextMessage = Annotated[
    Union[SystemMessage, HumanMessage, AIMessage],
    Field(discriminator="type"),
]

############################################################################################################


def get_buffer_string(
    messages: Sequence[BaseMessage],
    human_prefix: str = "Human",
    ai_prefix: str = "AI",
) -> str:
    """将消息序列转换为单一字符串（用于调试、日志或 prompt 拼接）

    Args:
        messages: 消息列表
        human_prefix: HumanMessage 的前缀，默认 "Human"
        ai_prefix: AIMessage 的前缀，默认 "AI"

    Returns:
        所有消息按 "角色: 内容" 格式拼接后的字符串

    Raises:
        ValueError: 遇到不支持的消息类型时

    Example:
        >>> msgs = [SystemMessage("你是助手"), HumanMessage("你好"), AIMessage("你好！")]
        >>> print(get_buffer_string(msgs))
        System: 你是助手
        Human: 你好
        AI: 你好！
    """
    lines: List[str] = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            role = human_prefix
        elif isinstance(msg, AIMessage):
            role = ai_prefix
        elif isinstance(msg, SystemMessage):
            role = "System"
        else:
            raise ValueError(f"不支持的消息类型: {type(msg)}")
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)
