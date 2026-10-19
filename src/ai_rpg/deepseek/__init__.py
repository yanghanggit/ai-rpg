"""DeepSeek provider 实现 + 默认 provider 绑定。

- `DeepSeekClient`：直连 DeepSeek 平台的实现（provider 私有细节都在这）；
- `DEEPSEEK_SERVICE`：全项目共用的默认实例（无状态，可复用）；
- `agent_loop` / `batch_complete`：已绑定默认实例的编排入口，业务系统只 import 它们，
  不重复做 provider 决策；
- 其它名字（工具类型 / 异常）转发自 `ai_rpg.llm`，只是为了让既有 import 不断。

与 provider 无关的编排（值对象 / 协议 / `chat_dump`）请直接从 `ai_rpg.llm` 取。
"""

from .agent_loop import (
    LOOP_END_ATTR,
    LOOP_ID_ATTR,
    AgentLoopResult,
    AgentLoopRound,
    agent_loop,
)
from .batch import batch_complete
from .client import (
    DEEPSEEK_SERVICE,
    DeepSeekClient,
    ToolCall,
    ToolDefinition,
    ToolFunction,
)
from .errors import DeepSeekError

__all__ = [
    "agent_loop",
    "AgentLoopResult",
    "AgentLoopRound",
    "batch_complete",
    "DEEPSEEK_SERVICE",
    "DeepSeekClient",
    "DeepSeekError",
    "LOOP_END_ATTR",
    "LOOP_ID_ATTR",
    "ToolCall",
    "ToolDefinition",
    "ToolFunction",
]
