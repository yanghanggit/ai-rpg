"""后台任务服务模块

本模块提供后台任务的管理接口，主要功能包括：
- 触发后台任务执行
- 查询任务执行状态（支持批量查询）
- 管理任务生命周期

主要端点：
- POST /api/tasks/v1/trigger: 触发新的后台任务
- GET /api/tasks/v1/status: 批量查询指定任务的执行状态

注意事项：
- 任务状态仅存储在内存中，服务重启后会丢失
- 当前实现为测试用途，模拟 5 秒的耗时任务
- 任务记录不会自动清理，需要手动管理
"""

import asyncio
from datetime import datetime
from typing import List
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
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
    """模拟耗时任务

    在后台执行一个模拟的耗时任务，用于测试后台任务机制。
    任务完成后会更新任务存储中的状态。

    Args:
        task_id: 任务唯一标识符
        duration: 任务持续时间（秒）
        game_server: 游戏服务器实例

    Note:
        - 任务执行期间会记录日志
        - 任务完成后状态会更新为 "completed"
        - 异常情况下状态会更新为 "failed"
    """
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
    """触发后台任务

    创建并启动一个新的后台任务。任务会在后台异步执行，
    不会阻塞当前请求的响应。

    Args:
        background_tasks: FastAPI 后台任务管理器
        game_server: 游戏服务器实例（依赖注入）

    Returns:
        TaskTriggerResponse: 包含任务ID和状态的响应对象

    Note:
        - 任务ID会自动生成（UUID格式）
        - 任务状态初始为 "running"
        - 可以通过返回的 task_id 查询任务执行状态
        - 当前实现的任务会模拟执行 5 秒
    """
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
    """批量查询任务状态

    根据提供的任务ID列表，批量查询任务的执行状态和详细信息。
    支持单个查询和批量查询。

    Args:
        task_ids: 要查询的任务ID列表，通过查询参数 task_ids 传递
        game_server: 游戏服务器实例（依赖注入）

    Returns:
        TasksStatusResponse: 任务状态响应，包含所有查询到的任务详情列表

    Raises:
        HTTPException(400): 未提供任务ID或任务ID列表为空

    Note:
        - 任务状态包括: "running", "completed", "failed"
        - 对于已完成的任务，会包含 end_time 字段
        - 对于失败的任务，会包含 error 字段
        - 如果某个任务ID不存在，会跳过该任务继续查询其他任务
        - 使用 Query 参数 task_ids 传递任务ID列表，例如：?task_ids=uuid1&task_ids=uuid2
        - 单个查询例如：?task_ids=uuid1
    """

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
