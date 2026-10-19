"""兼容出口：批量 chat 已搬到 `ai_rpg.llm.batch`。

真实实现在 `ai_rpg.llm.batch.batch_chat`（provider 无关，只依赖
`ChatClientProtocol` / `ChatError`）。这里只做转发，保持
`from ai_rpg.deepseek.batch import batch_chat` 等既有导入点可用。
"""

from ..llm.batch import batch_chat

__all__ = ["batch_chat"]
