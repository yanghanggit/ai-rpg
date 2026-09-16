"""批量（batch）行为工具函数。

提供批量并发图像生成 + 下载的封装。
"""

import asyncio
import time
from typing import Any, Coroutine, List, Optional, Tuple, TypeVar

from loguru import logger

T = TypeVar("T")


############################################################################################################
async def batch_generate_images(
    tasks: List[Tuple[str, Coroutine[Any, Any, T]]],
) -> List[Optional[T]]:
    """批量并发执行具名图像任务。

    任务列表需在调用方组装，每个元素为 ``(任务名, 协程)``；
    单个任务失败不影响其他任务，失败项结果记为 None，
    返回值与输入顺序一一对应。
    """
    if not tasks:
        return []

    logger.info(f"batch_generate_images: 启动 {len(tasks)} 个任务")

    start_time = time.time()
    results = await asyncio.gather(
        *[coro for _, coro in tasks],
        return_exceptions=True,
    )
    elapsed = time.time() - start_time

    outputs: List[Optional[T]] = []
    failed = 0
    for (name, _), result in zip(tasks, results):
        if isinstance(result, BaseException):
            logger.error(
                f"batch_generate_images '{name}' 失败: {type(result).__name__}: {result}"
            )
            outputs.append(None)
            failed += 1
        else:
            outputs.append(result)

    if failed:
        logger.warning(
            f"batch_generate_images: {failed}/{len(tasks)} 失败, 耗时 {elapsed:.2f}s"
        )
    else:
        logger.info(
            f"batch_generate_images: {len(tasks)}/{len(tasks)} 成功, 耗时 {elapsed:.2f}s"
        )
    return outputs
