"""对话抽象层（provider 无关）。

这里放「任何 LLM 供应商都能复用」的东西：数据类型、错误模型、客户端协议，
以及只依赖这些协议的编排代码（`agent_loop` / `batch_chat` / `chat_dump`）。
具体实现（当前是 DeepSeek）在 `ai_rpg.deepseek`；依赖方向永远是
`deepseek → llm`，本包**不得** import `ai_rpg.deepseek`。

`chat_dump` 作为子模块提供（`from ai_rpg.llm import chat_dump`），不在包 init
里 import：它带有开关状态与文件落盘副作用，按需导入即可。
"""

from .agent_loop import (
    LOOP_END_ATTR,
    LOOP_ID_ATTR,
    AgentLoopResult,
    AgentLoopRound,
    agent_loop,
)
from .batch import batch_chat
from .errors import ChatError, ErrorKind
from .protocol import ChatClientFactory, ChatClientProtocol, ChatResponseProtocol
from .types import (
    ReasoningEffort,
    ToolCall,
    ToolChoice,
    ToolDefinition,
    ToolFunction,
    Usage,
)

__all__ = [
    "AgentLoopResult",
    "AgentLoopRound",
    "ChatClientFactory",
    "ChatClientProtocol",
    "ChatError",
    "ChatResponseProtocol",
    "ErrorKind",
    "LOOP_END_ATTR",
    "LOOP_ID_ATTR",
    "ReasoningEffort",
    "ToolCall",
    "ToolChoice",
    "ToolDefinition",
    "ToolFunction",
    "Usage",
    "agent_loop",
    "batch_chat",
]
