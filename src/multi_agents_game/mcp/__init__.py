"""
MCP (Model Context Protocol) 模块

提供完整的 MCP 协议客户端实现，包括：
- MCP 客户端：处理与 MCP 服务器的通信
- 数据模型：MCP 协议中使用的数据结构
- 工具管理：MCP 工具的发现和调用
- 工具解析：解析LLM响应中的工具调用
- 工具执行：执行MCP工具并处理结果
- 提示构建：生成工具相关的提示信息
- 响应处理：处理和合成工具执行结果

主要特性：
- 基于 MCP 2025-06-18 规范
- 支持 Streamable HTTP 传输
- 异步操作支持
- 完整的错误处理
- 纯函数设计，框架无关
"""

from .client import McpClient
from .models import McpToolInfo, McpToolResult
from .parser import ToolCallParser
from .execution import initialize_mcp_client, execute_mcp_tool
from .prompts import build_json_tool_example, format_tool_description_simple
from .response import (
    remove_tool_call_markers,
    build_tool_results_section,
    build_standalone_tool_response,
    synthesize_response_with_tools,
)

__all__ = [
    # 客户端
    "McpClient",
    # 数据模型
    "McpToolInfo",
    "McpToolResult",
    # 解析器
    "ToolCallParser",
    # 执行相关
    "initialize_mcp_client",
    "execute_mcp_tool",
    # 提示构建
    "build_json_tool_example",
    "format_tool_description_simple",
    # 响应处理
    "remove_tool_call_markers",
    "build_tool_results_section",
    "build_standalone_tool_response",
    "synthesize_response_with_tools",
]
