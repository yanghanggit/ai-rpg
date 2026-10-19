"""DeepSeek provider 实现 + 默认 provider 绑定。

- `DeepSeekClient`：直连 DeepSeek 平台的实现（provider 私有细节都在这）；
- `agent_loop`：`ai_rpg.llm.agent_loop` 的 DeepSeek 绑定版本，这是全项目唯一的
  「用哪个 provider」决策点（业务系统只 import 它，不关心绑定过程）；
- 其它名字（工具类型 / 异常）都转发自 `ai_rpg.llm`，只是为了让既有 import 不断。

与 provider 无关的编排（`batch_chat` / `chat_dump`）请直接从 `ai_rpg.llm` 取。
"""

from .agent_loop import (
    LOOP_END_ATTR,
    LOOP_ID_ATTR,
    AgentLoopResult,
    AgentLoopRound,
    agent_loop,
)
from .client import DeepSeekClient, ToolCall, ToolDefinition, ToolFunction
from .errors import DeepSeekError

__all__ = [
    "agent_loop",
    "AgentLoopResult",
    "AgentLoopRound",
    "LOOP_END_ATTR",
    "LOOP_ID_ATTR",
    "DeepSeekClient",
    "DeepSeekError",
    "ToolCall",
    "ToolDefinition",
    "ToolFunction",
]
