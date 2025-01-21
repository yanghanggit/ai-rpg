from typing import List, Any
from agent.task_request_handler import TaskRequestHandler
from loguru import logger
import asyncio
import time


async def gather(task_request_handlers: List[TaskRequestHandler]) -> List[Any]:
    if len(task_request_handlers) == 0:
        return []

    coros = [task.a_request() for task in task_request_handlers]

    start_time = time.time()
    future = await asyncio.gather(*coros)
    end_time = time.time()

    logger.debug(f"task_request_utils.gather:{end_time - start_time:.2f} seconds")
    return future
