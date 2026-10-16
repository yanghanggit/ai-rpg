"""Chat services module for handling AI chat functionality."""

from .agent_loop import (
    LOOP_END_ATTR,
    LOOP_ID_ATTR,
    AgentLoopResult,
    AgentLoopRound,
    agent_loop,
)
from .batch import batch_chat
from .client import DeepSeekClient, ToolCall, ToolDefinition, ToolFunction
from .errors import DeepSeekError

__all__ = [
    "agent_loop",
    "AgentLoopRound",
    "AgentLoopResult",
    "LOOP_ID_ATTR",
    "LOOP_END_ATTR",
    "batch_chat",
    "DeepSeekClient",
    "DeepSeekError",
    "ToolFunction",
    "ToolDefinition",
    "ToolCall",
]
