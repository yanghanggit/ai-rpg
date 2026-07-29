"""后台任务服务模块"""

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator, List
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger
from ..models import (
    TaskTriggerResponse,
    TaskRecord,
    TasksStatusResponse,
    TaskStatus,
)
from ..services.game_server_dependencies import CurrentGameServer
from ..game.game_server import GameServer

################################################################################################################
background_tasks_api_router = APIRouter()


###############################################################################################################################################
################################################################################################################
################################################################################################################


async def simulate_long_task(
    task_id: str, duration: int, game_server: GameServer
) -> None:
    """模拟耗时任务"""
    try:
        logger.info(f"🚀 后台任务开始: task_id={task_id}, duration={duration}s")
        await asyncio.sleep(duration)

        task = game_server.get_task(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.end_time = datetime.now().isoformat()

        logger.info(f"✅ 后台任务完成: task_id={task_id}")
    except Exception as e:
        logger.error(f"❌ 后台任务失败: task_id={task_id}, error={e}")
        task = game_server.get_task(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.end_time = datetime.now().isoformat()
            task.error = str(e)


################################################################################################################
################################################################################################################
################################################################################################################


@background_tasks_api_router.post(
    path="/api/tasks/v1/trigger", response_model=TaskTriggerResponse
)
async def trigger_background_task(
    background_tasks: BackgroundTasks,
    game_server: CurrentGameServer,
) -> TaskTriggerResponse:
    """触发后台任务"""
    # 使用 GameServer 创建任务记录
    task_record = game_server.create_task()

    # 添加模拟任务：等待 5 秒
    logger.warning(
        "⚠️ 注意：当前后台任务为测试实现，模拟 5 秒耗时任务!!!!!!!!!!!!!!!!!!!"
    )
    background_tasks.add_task(simulate_long_task, task_record.task_id, 5, game_server)

    logger.info(f"📝 创建后台任务: task_id={task_record.task_id}")

    return TaskTriggerResponse(
        task_id=task_record.task_id,
        status=task_record.status.value,
        message="后台任务已启动",
    )


################################################################################################################
################################################################################################################
################################################################################################################


@background_tasks_api_router.get(
    path="/api/tasks/v1/status", response_model=TasksStatusResponse
)
async def get_tasks_status(
    game_server: CurrentGameServer,
    task_ids: List[str] = Query(..., alias="task_ids"),
) -> TasksStatusResponse:
    """批量查询任务状态"""

    logger.info(f"🔍 批量查询任务状态: task_ids={task_ids}")

    # 验证请求参数
    if len(task_ids) == 0 or task_ids[0] == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供至少一个任务ID",
        )

    # 批量查询任务
    tasks_details: List[TaskRecord] = []

    for task_id in task_ids:
        task_detail = game_server.get_task(task_id)
        if task_detail is None:
            logger.warning(f"⚠️ 查询的任务不存在: task_id={task_id}")
            continue  # 跳过不存在的任务

        logger.info(
            f"🔍 查询到任务状态: task_id={task_id}, status={task_detail.status}"
        )

        tasks_details.append(task_detail)

    return TasksStatusResponse(tasks=tasks_details)


################################################################################################################
################################################################################################################
################################################################################################################


@background_tasks_api_router.get(path="/api/tasks/v1/watch/{task_id}")
async def watch_task(
    task_id: str,
    game_server: CurrentGameServer,
    timeout_seconds: int = Query(default=120, ge=1, le=600),
    interval: float = Query(default=0.3, ge=0.1, le=5.0),
) -> StreamingResponse:
    """SSE 端点：推送单个任务状态直至终态或超时。"""

    async def event_generator(poll_interval: float) -> AsyncGenerator[str, None]:
        elapsed = 0.0
        while elapsed < timeout_seconds:
            task = game_server.get_task(task_id)
            if task is None:
                payload = json.dumps({"error": "task_not_found", "task_id": task_id})
                yield f"data: {payload}\n\n"
                logger.warning(f"watch_task: 任务不存在 task_id={task_id}")
                return
            yield f"data: {task.model_dump_json()}\n\n"
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                logger.info(
                    f"watch_task: 任务终态 task_id={task_id} status={task.status}"
                )
                return
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        payload = json.dumps({"error": "timeout", "task_id": task_id})
        yield f"data: {payload}\n\n"
        logger.warning(f"watch_task: 超时 task_id={task_id}")

    return StreamingResponse(event_generator(interval), media_type="text/event-stream")
