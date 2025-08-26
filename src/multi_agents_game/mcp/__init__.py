"""
MCP (Model Context Protocol) 模块

提供完整的 MCP 协议客户端实现，包括：
- MCP 客户端：处理与 MCP 服务器的通信
- 数据模型：MCP 协议中使用的数据结构
- 工具管理：MCP 工具的发现和调用

主要特性：
- 基于 MCP 2025-06-18 规范
- 支持 Streamable HTTP 传输
- 异步操作支持
- 完整的错误处理
"""

from .client import McpClient
from .models import McpToolInfo, McpToolResult

__all__ = [
    # 客户端
    "McpClient",
    # 数据模型
    "McpToolInfo",
    "McpToolResult",
]
