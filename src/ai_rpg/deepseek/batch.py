"""DeepSeek 绑定入口：把 `ai_rpg.llm.batch.batch_complete` 绑定到 `DEEPSEEK_SERVICE`。

分工与 `deepseek/agent_loop.py` 一致：编排在抽象层，provider 选择只在本包决定一次。
业务侧因此不需要自己持有 service 实例。
"""

from typing import List, Sequence

from ..llm.batch import batch_complete as _batch_complete
from ..llm.types import ChatCompletionRequest, ChatCompletionResult
from .client import DEEPSEEK_SERVICE

__all__ = ["batch_complete"]


############################################################################################################
async def batch_complete(
    requests: Sequence[ChatCompletionRequest],
    *,
    max_concurrency: int = 2,
) -> List[ChatCompletionResult]:
    """`ai_rpg.llm.batch.batch_complete` 的 DeepSeek 绑定版本（参数语义完全相同）。"""
    return await _batch_complete(
        DEEPSEEK_SERVICE, requests, max_concurrency=max_concurrency
    )
