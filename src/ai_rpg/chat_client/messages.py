"""自定义消息类型（仿 langchain 风格，无 langchain 依赖）

提供与 langchain_core.messages 接口兼容的消息类型：
- BaseMessage
- SystemMessage
- HumanMessage
- AIMessage
"""

from typing import Any, Dict
from pydantic import BaseModel, Field


############################################################################################################
class BaseMessage(BaseModel):
    """消息基类"""

    type: str
    content: str = ""
    additional_kwargs: Dict[str, Any] = Field(default_factory=dict)


############################################################################################################
class SystemMessage(BaseMessage):
    """系统提示消息"""

    type: str = "system"

    def __init__(self, content: str = "", **kwargs: Any) -> None:
        super().__init__(type="system", content=content, **kwargs)


############################################################################################################
class HumanMessage(BaseMessage):
    """用户消息"""

    type: str = "human"

    def __init__(self, content: str = "", **kwargs: Any) -> None:
        super().__init__(type="human", content=content, **kwargs)


############################################################################################################
class AIMessage(BaseMessage):
    """AI 回复消息"""

    type: str = "ai"

    def __init__(self, content: str = "", **kwargs: Any) -> None:
        super().__init__(type="ai", content=content, **kwargs)
