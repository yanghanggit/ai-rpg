"""
MCP (Model Context Protocol) 数据模型

定义 MCP 协议中使用的数据结构和模型类。
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel


class McpToolInfo(BaseModel):
    """MCP 工具信息"""

    name: str
    description: str
    input_schema: Dict[str, Any]


class McpToolResult(BaseModel):
    """MCP 工具执行结果"""

    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float
