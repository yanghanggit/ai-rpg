"""通用批量并发工具函数。"""

import asyncio
import time
from typing import Any, Coroutine, List, Tuple

from loguru import logger


############################################################################################################
async def batch_run_boolean_tasks(
    tasks: List[Tuple[str, Coroutine[Any, Any, Any]]],
) -> List[bool]:
    """批量并发执行具名任务，按真值归约为成功/失败。

    任务列表需在调用方组装，每个元素为 ``(任务名, 协程)``；每个协程的返回值取其
    真值（``bool(result)``）作为结果，因此协程可返回任意类型（含实现了 ``__bool__``
    的结果对象）。返回值按输入顺序对应每个任务的成功/失败结果。
    """
    if not tasks:
        return []

    logger.info(f"batch_run_boolean_tasks: 启动 {len(tasks)} 个任务")

    start_time = time.time()
    results = await asyncio.gather(
        *[coro for _, coro in tasks],
        return_exceptions=True,
    )
    elapsed = time.time() - start_time

    outcomes: List[bool] = []
    for (name, _), result in zip(tasks, results):
        if isinstance(result, BaseException):
            logger.error(
                f"batch_run_boolean_tasks '{name}' 异常: {type(result).__name__}: {result}"
            )
            outcomes.append(False)
        else:
            logger.info(
                f"batch_run_boolean_tasks '{name}': {'成功' if result else '失败'}"
            )
            outcomes.append(bool(result))

    succeeded = sum(1 for o in outcomes if o)
    logger.info(
        f"batch_run_boolean_tasks: {succeeded}/{len(tasks)} 成功, {elapsed:.2f}s"
    )
    return outcomes


############################################################################################################
