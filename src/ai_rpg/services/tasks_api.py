"""任务状态查询接口模块

状态不持久化，每次查询时从 Procrastinate 实时读取；仅失败时的错误文本被
持久化在 `task_errors` 表中（Procrastinate 自己的表不记录异常内容）。
"""

import asyncio
import json
from typing import Annotated, AsyncGenerator, List

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from procrastinate.exceptions import NoResult
from procrastinate.jobs import Status as ProcrastinateJobStatus

from ..models import TasksStatusResponse, TaskStatusView
from ..pgsql import get_task_error, procrastinate_app

################################################################################################################
tasks_api_router = APIRouter()


###############################################################################################################################################
async def get_task_status_view(job_id: int) -> TaskStatusView:
    """查询指定任务的当前状态视图；job 不存在时由 Procrastinate 抛出 NoResult"""

    status = await procrastinate_app.job_manager.get_job_status_async(job_id)

    error = get_task_error(job_id) if status == ProcrastinateJobStatus.FAILED else None

    return TaskStatusView(job_id=job_id, status=status, error=error)


################################################################################################################
################################################################################################################
################################################################################################################


@tasks_api_router.get(path="/api/tasks/v1/status", response_model=TasksStatusResponse)
async def get_tasks_status(
    job_ids: Annotated[List[int], Query(alias="job_ids")],
) -> TasksStatusResponse:
    """批量查询任务状态；不存在的 job_id 会被跳过"""

    logger.info(f"🔍 批量查询任务状态: job_ids={job_ids}")

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


@tasks_api_router.get(path="/api/tasks/v1/watch/{job_id}")
async def watch_task(
    job_id: int,
    timeout_seconds: int = Query(default=120, ge=1, le=600),
    interval: float = Query(default=0.3, ge=0.1, le=5.0),
) -> StreamingResponse:
    """SSE 端点：推送单个任务状态直至终态或超时。"""

    async def event_generator(poll_interval: float) -> AsyncGenerator[str, None]:

        elapsed = 0.0
        while elapsed < timeout_seconds:

            try:
                # 查询任务的当前状态
                task = await get_task_status_view(job_id)
            except NoResult:

                # 任务不存在，发送错误事件并终止生成器
                payload = json.dumps({"error": "task_not_found", "job_id": job_id})
                yield f"data: {payload}\n\n"
                logger.warning(f"watch_task: 任务不存在 job_id={job_id}")
                return

            yield f"data: {task.model_dump_json()}\n\n"
            if task.status in (
                ProcrastinateJobStatus.SUCCEEDED,
                ProcrastinateJobStatus.FAILED,
            ):
                logger.info(
                    f"watch_task: 任务终态 job_id={job_id} status={task.status}"
                )
                return

            # 等待下一次轮询
            await asyncio.sleep(poll_interval)

            # 更新已用时间
            elapsed += poll_interval

        # 超时处理
        payload = json.dumps({"error": "timeout", "job_id": job_id})
        yield f"data: {payload}\n\n"
        logger.warning(f"watch_task: 超时 job_id={job_id}")

    return StreamingResponse(event_generator(interval), media_type="text/event-stream")
