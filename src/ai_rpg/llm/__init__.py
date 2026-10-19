"""chat completion 抽象层（provider 无关）。

命名对齐 OpenAI / DeepSeek 的 ``POST /chat/completions``：一次调用 = 请求模型补全
下一条 assistant 消息，因此类型与入口都叫 completion 而不是笼统的 chat。

这里放「任何 LLM 供应商都能复用」的东西：

- 值对象：`ChatCompletionRequest`（问什么）/ `ChatCompletionResult`（补全出什么）；
- 协议：`ChatCompletionService`（执行者，方法为 `complete()`）；
- 错误模型：`ChatError`；
- 只依赖上述契约的编排：`agent_loop` / `batch_complete` / `chat_dump`。

具体实现（当前是 DeepSeek）在 `ai_rpg.deepseek`；依赖方向永远是
`deepseek → llm`，本包**不得** import `ai_rpg.deepseek`。

`chat_dump` 作为子模块提供（`from ai_rpg.llm import chat_dump`），不在包 init
里 import：它带有开关与文件落盘副作用，按需导入即可。
"""

from .agent_loop import (
    LOOP_END_ATTR,
    LOOP_ID_ATTR,
    AgentLoopResult,
    AgentLoopRound,
    agent_loop,
)
from .batch import batch_complete
from .errors import ChatError, ErrorKind
from .protocol import ChatCompletionService
from .types import (
    ChatCompletionRequest,
    ChatCompletionResult,
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
    "ChatError",
    "ChatCompletionRequest",
    "ChatCompletionResult",
    "ChatCompletionService",
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
    "batch_complete",
]
