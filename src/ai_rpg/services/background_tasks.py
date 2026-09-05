"""后台任务服务模块"""

import asyncio
import json
from typing import AsyncGenerator, List
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger
from procrastinate.exceptions import NoResult
from ..pgsql import procrastinate_app
from ..models import (
    BackgroundTaskStatus,
    TaskTriggerResponse,
    TaskStatusView,
    TasksStatusResponse,
)
from .task_status import get_task_status_view

################################################################################################################
background_tasks_api_router = APIRouter()


###############################################################################################################################################
################################################################################################################
################################################################################################################


@procrastinate_app.task(queue="game")
async def simulate_long_task(duration: int) -> None:
    """模拟耗时任务"""
    logger.info(f"🚀 后台任务开始: duration={duration}s")
    await asyncio.sleep(duration)
    logger.info("✅ 后台任务完成")


################################################################################################################
################################################################################################################
################################################################################################################


@background_tasks_api_router.post(
    path="/api/tasks/v1/trigger", response_model=TaskTriggerResponse
)
async def trigger_background_task() -> TaskTriggerResponse:
    """触发后台任务"""
    # 添加模拟任务：等待 5 秒
    logger.warning(
        "⚠️ 注意：当前后台任务为测试实现，模拟 5 秒耗时任务!!!!!!!!!!!!!!!!!!!"
    )
    deferred_job_id = await simulate_long_task.defer_async(duration=5)
    job_id = str(deferred_job_id)

    logger.info(f"📝 创建后台任务: job_id={job_id}")

    return TaskTriggerResponse(
        job_id=job_id,
        status=BackgroundTaskStatus.RUNNING.value,
        message="后台任务已启动",
    )


################################################################################################################
################################################################################################################
################################################################################################################


@background_tasks_api_router.get(
    path="/api/tasks/v1/status", response_model=TasksStatusResponse
)
async def get_tasks_status(
    job_ids: List[str] = Query(..., alias="job_ids"),
) -> TasksStatusResponse:
    """批量查询任务状态"""

    logger.info(f"🔍 批量查询任务状态: job_ids={job_ids}")

    # 验证请求参数
    if len(job_ids) == 0 or job_ids[0] == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供至少一个任务ID",
        )

    # 批量查询任务
    tasks_details: List[TaskStatusView] = []

    for job_id in job_ids:
        try:
            task_detail = await get_task_status_view(job_id)
        except NoResult:
            logger.warning(f"⚠️ 查询的任务不存在: job_id={job_id}")
            continue  # 跳过不存在的任务

        logger.info(f"🔍 查询到任务状态: job_id={job_id}, status={task_detail.status}")

        tasks_details.append(task_detail)

    return TasksStatusResponse(tasks=tasks_details)


################################################################################################################
################################################################################################################
################################################################################################################


@background_tasks_api_router.get(path="/api/tasks/v1/watch/{job_id}")
async def watch_task(
    job_id: str,
    timeout_seconds: int = Query(default=120, ge=1, le=600),
    interval: float = Query(default=0.3, ge=0.1, le=5.0),
) -> StreamingResponse:
    """SSE 端点：推送单个任务状态直至终态或超时。"""

    async def event_generator(poll_interval: float) -> AsyncGenerator[str, None]:
        elapsed = 0.0
        while elapsed < timeout_seconds:
            try:
                task = await get_task_status_view(job_id)
            except NoResult:
                payload = json.dumps({"error": "task_not_found", "job_id": job_id})
                yield f"data: {payload}\n\n"
                logger.warning(f"watch_task: 任务不存在 job_id={job_id}")
                return
            yield f"data: {task.model_dump_json()}\n\n"
            if task.status in (
                BackgroundTaskStatus.COMPLETED,
                BackgroundTaskStatus.FAILED,
            ):
                logger.info(
                    f"watch_task: 任务终态 job_id={job_id} status={task.status}"
                )
                return
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        payload = json.dumps({"error": "timeout", "job_id": job_id})
        yield f"data: {payload}\n\n"
        logger.warning(f"watch_task: 超时 job_id={job_id}")

    return StreamingResponse(event_generator(interval), media_type="text/event-stream")
