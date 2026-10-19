"""对话抽象层（provider 无关）。

这里放「任何 LLM 供应商都能复用」的东西：数据类型、错误模型、客户端协议。
具体实现（当前是 DeepSeek）在 `ai_rpg.deepseek`；依赖方向永远是
`deepseek → llm`，本包**不得** import `ai_rpg.deepseek`。

注意：`agent_loop` / `batch_chat` / `chat_dump` 目前仍在 `ai_rpg.deepseek`，
它们已经只依赖协议（可直接搬到本包），迁移留给下一步。
"""

from .errors import ChatError, ErrorKind
from .protocol import (
    ChatClientFactory,
    ChatClientProtocol,
    ChatResponseProtocol,
    ModelCatalog,
)
from .types import (
    ReasoningEffort,
    ToolCall,
    ToolChoice,
    ToolDefinition,
    ToolFunction,
    Usage,
)

__all__ = [
    "ChatClientFactory",
    "ChatClientProtocol",
    "ChatError",
    "ChatResponseProtocol",
    "ErrorKind",
    "ModelCatalog",
    "ReasoningEffort",
    "ToolCall",
    "ToolChoice",
    "ToolDefinition",
    "ToolFunction",
    "Usage",
]
