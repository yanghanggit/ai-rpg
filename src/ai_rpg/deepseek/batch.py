"""批量（batch）行为工具函数。

提供批量并发 chat 与批量并发 agent_loop 的封装。
"""

import asyncio
import time
from typing import List, Optional, Sequence

import httpx
from loguru import logger

from ..llm.protocol import ChatClientProtocol
from .errors import DeepSeekError


############################################################################################################
async def batch_chat(
    clients: Sequence[ChatClientProtocol],
    *,
    max_concurrency: int = 2,
) -> List[Optional[DeepSeekError]]:
    """批量并发发送聊天请求。

    创建一个共享 httpx.AsyncClient，所有 chat() 复用同一连接池，
    batch 结束后自动关闭。

    ``max_concurrency`` 用信号量限制同时在飞的请求数（默认 2）：避免一次性
    把全部请求打给 DeepSeek 而触发服务端限流。它只限「并发数」不限「速率」。

    返回与 ``clients`` 按 index 对齐的失败列表：成功项为 None，失败项为
    对应的 DeepSeekError（与各 client 的 ``.error`` 为同一对象）。通讯层
    不做重试，是否重试由业务层据 ``DeepSeekError.retryable`` 决定。

    入参类型是 ``ChatClientProtocol`` 而非具体实现，且声明为 ``Sequence``：批量通讯只
    依赖协议的 ``label`` / ``error`` / ``chat()``，换成任何 provider 都不用改这里；
    ``Sequence`` 是协变的，因此 ``list[DeepSeekClient]`` 可直接传入。
    """
    if not clients:
        return []
    assert max_concurrency >= 1, "max_concurrency 必须 >= 1"

    # 记录批量请求开始时间。
    start_time = time.time()

    # 使用共享的 httpx.AsyncClient，并以信号量限制同时在飞的请求数。
    async with httpx.AsyncClient() as shared_client:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _guarded(client: ChatClientProtocol) -> None:
            """拿不到许可证就在这里排队，保证任意时刻至多 max_concurrency 个请求在飞。"""
            async with semaphore:
                await client.chat(client=shared_client)

        results = await asyncio.gather(
            *[_guarded(c) for c in clients],
            return_exceptions=True,
        )

    # 记录批量请求耗时。
    elapsed = time.time() - start_time
    logger.debug(f"batch_chat: {len(clients)} clients, {elapsed:.2f}s")

    # 遍历每个请求的结果，处理异常情况。
    for i, result in enumerate(results):
        # 处理每个请求的异常情况。
        if isinstance(result, Exception):
            name = clients[i].label if i < len(clients) else "unknown"
            logger.error(
                f"Request failed for '{name}': {type(result).__name__}: {result}"
            )

    # 统计批量请求失败的数量。
    failed = sum(1 for r in results if isinstance(r, BaseException))
    if failed:
        logger.warning(f"batch_chat: {failed}/{len(clients)} failed")
    else:
        logger.debug(f"batch_chat: all {len(clients)} requests succeeded")

    # 返回与入参对齐的失败列表（成功为 None）。优先取 client 自身记录的 error，
    # 兜底用 gather 的原始异常，覆盖 chat() 之外抛出的 BaseException。
    errors: List[Optional[DeepSeekError]] = []
    for client, result in zip(clients, results):
        if client.error is not None:
            # 如果 client 自身记录了 error，则直接使用该 error。
            errors.append(client.error)
        elif isinstance(result, DeepSeekError):
            # 如果 gather 捕获了 DeepSeekError，则使用该 error。
            errors.append(result)
        elif isinstance(result, BaseException):
            # 如果 gather 捕获了其他类型的 BaseException，则将其封装为 DeepSeekError。
            errors.append(
                DeepSeekError(
                    client.label, f"{type(result).__name__}: {result}", kind="api"
                )
            )
        else:
            # 如果以上条件都不满足，则认为该请求成功，记录为 None。
            errors.append(None)

    return errors
