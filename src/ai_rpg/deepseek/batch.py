"""批量（batch）行为工具函数。

提供批量并发 chat 与批量并发 agent_loop 的封装。
"""

import asyncio
import time
from typing import List

import httpx
from loguru import logger

from .client import DeepSeekClient


############################################################################################################
async def batch_chat(clients: List[DeepSeekClient]) -> None:
    """批量并发发送聊天请求。

    创建一个共享 httpx.AsyncClient，所有 chat() 复用同一连接池，
    batch 结束后自动关闭。
    """
    if not clients:
        return

    start_time = time.time()
    async with httpx.AsyncClient() as shared_client:
        results = await asyncio.gather(
            *[c.chat(client=shared_client) for c in clients],
            return_exceptions=True,
        )
    elapsed = time.time() - start_time
    logger.debug(f"batch_chat: {len(clients)} clients, {elapsed:.2f}s")

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            name = clients[i].name if i < len(clients) else "unknown"
            logger.error(
                f"Request failed for '{name}': {type(result).__name__}: {result}"
            )

    failed = sum(1 for r in results if isinstance(r, BaseException))
    if failed:
        logger.warning(f"batch_chat: {failed}/{len(clients)} failed")
    else:
        logger.debug(f"batch_chat: all {len(clients)} requests succeeded")
