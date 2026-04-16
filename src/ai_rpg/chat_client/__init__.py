"""Chat services module for handling AI chat functionality.

Note: Routing functionality has been moved to the rag module.
Please use: from ai_rpg.rag.routing import RouteDecisionManager
"""

from .protocol import ChatRequest, ChatResponse
from .client import ChatClient
from .deepseek_client import DeepSeekClient
from ..models.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    get_buffer_string,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "ChatClient",
    "DeepSeekClient",
    "BaseMessage",
    "SystemMessage",
    "HumanMessage",
    "AIMessage",
    "get_buffer_string",
]
