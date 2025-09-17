"""
Azure OpenAI GPT聊天模块

该模块提供基于Azure OpenAI GPT的聊天功能，包括：
- 基础聊天图（chat_graph.py）
- RAG 增强聊天图（rag_graph.py）
- MCP 客户端聊天图（mcp_client_graph.py）
- 统一聊天图（unified_chat_graph.py）
"""

from .chat_graph import (
    State,
    create_compiled_stage_graph,
    stream_graph_updates,
)
from .rag_graph import create_rag_compiled_graph, stream_rag_graph_updates
from .mcp_client_graph import (
    create_compiled_mcp_stage_graph,
    stream_mcp_graph_updates,
    McpState,
)
from .unified_chat_graph import (
    create_unified_chat_graph,
    stream_unified_graph_updates,
    UnifiedState,
)
from .client import create_azure_openai_gpt_llm

__all__ = [
    # 基础聊天图
    "State",
    "create_compiled_stage_graph",
    "stream_graph_updates",
    # RAG 聊天图
    "create_rag_compiled_graph",
    "stream_rag_graph_updates",
    # MCP 客户端聊天图
    "create_compiled_mcp_stage_graph",
    "stream_mcp_graph_updates",
    "McpState",
    # 统一聊天图
    "create_unified_chat_graph",
    "stream_unified_graph_updates",
    "UnifiedState",
    # Azure OpenAI GPT 客户端
    "create_azure_openai_gpt_llm",
]
