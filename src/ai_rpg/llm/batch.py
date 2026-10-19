"""批量（batch）并发 chat completion（provider 无关）。

入参是「一个无状态 service + 一批 completion 请求」，出参是与请求**按顺序对齐**
的结果列表。
结果自带 ``error``，因此调用方不需要再拿 client 对象去对账（旧实现返回
``List[Optional[ChatError]]``，调用方必须 ``zip(clients, errors)`` 才知道哪条失败）。

本模块**不得** import `ai_rpg.deepseek`：只依赖 `ChatCompletionService` /
`ChatCompletionRequest` / `ChatCompletionResult` / `ChatError`。
"""

import asyncio
import time
from typing import List, Sequence

from loguru import logger

from .errors import ChatError
from .protocol import ChatCompletionService
from .types import ChatCompletionRequest, ChatCompletionResult


############################################################################################################
async def batch_complete(
    service: ChatCompletionService,
    requests: Sequence[ChatCompletionRequest],
    *,
    max_concurrency: int = 2,
) -> List[ChatCompletionResult]:
    """并发发送一批 chat completion 请求，返回与 ``requests`` 等长且同序的结果。

    ``max_concurrency`` 用信号量限制同时在飞的请求数（默认 2）：避免一次性
    把全部请求打给服务端而触发限流。它只限「并发数」不限「速率」。

    ``ChatCompletionService.chat`` 对预期内失败不抛异常，因此结果天然带 ``error``；
    意外异常（bug）也会被收敛成 ``error``，保证返回长度与入参一致（取消 /
    ``BaseException`` 除外，照常向上传播）。
    """
    if not requests:
        return []
    assert max_concurrency >= 1, "max_concurrency 必须 >= 1"

    start_time = time.time()
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _guarded(request: ChatCompletionRequest) -> ChatCompletionResult:
        """拿不到许可证就在这里排队，保证任意时刻至多 max_concurrency 个请求在飞。"""
        async with semaphore:
            try:
                return await service.complete(request)
            except Exception as e:
                # 意外异常也收敛成结果，保持「单一失败通道 + 等长返回」
                return ChatCompletionResult(
                    request=request,
                    error=ChatError(
                        request.label, f"{type(e).__name__}: {e}", kind="api"
                    ),
                )

    results = await asyncio.gather(*[_guarded(request) for request in requests])

    elapsed = time.time() - start_time
    logger.debug(f"batch_complete: {len(requests)} requests, {elapsed:.2f}s")

    failed = [result.label for result in results if result.error is not None]
    if failed:
        logger.warning(
            f"batch_complete: {len(failed)}/{len(requests)} failed: {failed}"
        )
    else:
        logger.debug(f"batch_complete: all {len(requests)} requests succeeded")

    return results
