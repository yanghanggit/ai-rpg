"""后台任务服务模块

本模块提供后台任务的管理接口，主要功能包括：
- 触发后台任务执行
- 查询任务执行状态
- 管理任务生命周期

主要端点：
- POST /api/tasks/v1/trigger: 触发新的后台任务
- GET /api/tasks/v1/status/{task_id}: 查询指定任务的执行状态

注意事项：
- 任务状态仅存储在内存中，服务重启后会丢失
- 当前实现为测试用途，模拟 5 秒的耗时任务
- 任务记录不会自动清理，需要手动管理
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum, unique
from typing import Dict, Optional, final
from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger
from ..models import (
    TaskTriggerResponse,
    TaskStatusResponse,
)

################################################################################################################
background_tasks_api_router = APIRouter()


###############################################################################################################################################
@final
@unique
class TaskStatus(StrEnum):
    """任务状态枚举

    定义后台任务的所有可能状态
    """

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


###############################################################################################################################################
@dataclass
class TaskInfo:
    """任务信息数据类

    存储单个后台任务的状态和执行信息

    Attributes:
        status: 任务状态
        start_time: 任务开始时间
        end_time: 任务结束时间（可选）
        error: 错误信息（可选）
    """

    status: TaskStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    error: Optional[str] = None


# 内存存储任务状态（简单测试用）
task_store: Dict[str, TaskInfo] = {}

################################################################################################################
################################################################################################################
################################################################################################################


async def simulate_long_task(task_id: str, duration: int = 5) -> None:
    """模拟耗时任务

    在后台执行一个模拟的耗时任务，用于测试后台任务机制。
    任务完成后会更新任务存储中的状态。

    Args:
        task_id: 任务唯一标识符
        duration: 任务持续时间（秒），默认 5 秒

    Note:
        - 任务执行期间会记录日志
        - 任务完成后状态会更新为 "completed"
        - 异常情况下状态会更新为 "failed"
    """
    try:
        logger.info(f"🚀 后台任务开始: task_id={task_id}, duration={duration}s")
        await asyncio.sleep(duration)

        task_store[task_id].status = TaskStatus.COMPLETED
        task_store[task_id].end_time = datetime.now()

        logger.info(f"✅ 后台任务完成: task_id={task_id}")
    except Exception as e:
        logger.error(f"❌ 后台任务失败: task_id={task_id}, error={e}")
        task_store[task_id].status = TaskStatus.FAILED
        task_store[task_id].end_time = datetime.now()
        task_store[task_id].error = str(e)


################################################################################################################
################################################################################################################
################################################################################################################


@background_tasks_api_router.post(
    path="/api/tasks/v1/trigger", response_model=TaskTriggerResponse
)
async def trigger_background_task(
    background_tasks: BackgroundTasks,
) -> TaskTriggerResponse:
    """触发后台任务

    创建并启动一个新的后台任务。任务会在后台异步执行，
    不会阻塞当前请求的响应。

    Args:
        background_tasks: FastAPI 后台任务管理器

    Returns:
        TaskTriggerResponse: 包含任务ID和状态的响应对象

    Note:
        - 任务ID会自动生成（UUID格式）
        - 任务状态初始为 "running"
        - 可以通过返回的 task_id 查询任务执行状态
        - 当前实现的任务会模拟执行 5 秒
    """
    task_id = str(uuid.uuid4())
    task_store[task_id] = TaskInfo(
        status=TaskStatus.RUNNING,
        start_time=datetime.now(),
    )

    # 添加模拟任务：等待 5 秒
    background_tasks.add_task(simulate_long_task, task_id, 5)

    logger.info(f"📝 创建后台任务: task_id={task_id}")

    return TaskTriggerResponse(
        task_id=task_id,
        status=task_store[task_id].status.value,
        message="后台任务已启动",
    )


################################################################################################################
################################################################################################################
################################################################################################################


@background_tasks_api_router.get(
    path="/api/tasks/v1/status/{task_id}", response_model=TaskStatusResponse
)
async def get_task_status(
    task_id: str,
) -> TaskStatusResponse:
    """查询任务状态

    根据任务ID查询指定任务的执行状态和详细信息。

    Args:
        task_id: 任务唯一标识符

    Returns:
        TaskStatusResponse: 包含任务状态、开始时间、结束时间等信息的响应对象

    Raises:
        HTTPException: 当任务ID不存在时返回 404 错误

    Note:
        - 任务状态包括: "running", "completed", "failed"
        - 对于已完成的任务，会包含 end_time 字段
        - 对于失败的任务，会包含 error 字段
    """
    if task_id not in task_store:
        logger.warning(f"⚠️ 查询的任务不存在: task_id={task_id}")
        raise HTTPException(status_code=404, detail="任务不存在")

    task_info = task_store[task_id]
    logger.info(f"🔍 查询任务状态: task_id={task_id}, status={task_info.status}")

    return TaskStatusResponse(
        task_id=task_id,
        status=task_info.status.value,
        start_time=task_info.start_time.isoformat(),
        end_time=(
            task_info.end_time.isoformat() if task_info.end_time is not None else ""
        ),
        error=task_info.error if task_info.error is not None else "",
    )
