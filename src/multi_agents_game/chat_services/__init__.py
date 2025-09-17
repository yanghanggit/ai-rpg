"""Chat services module for handling AI chat functionality.

Note: Routing functionality has been moved to the rag module.
Please use: from multi_agents_game.rag.routing import RouteDecisionManager
"""

from .protocol import ChatRequest, ChatResponse
from .client import ChatClient

# from .manager import ChatClientManager

__all__ = [
    # "ChatClientManager",
    "ChatRequest",
    "ChatResponse",
    "ChatClient",
]
