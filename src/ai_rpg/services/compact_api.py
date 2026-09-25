"""
上下文压缩 API 路由模块

提供手动触发指定实体上下文压缩的接口（与场景状态无关）。
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ..models import (
    CompactContextRequest,
    CompactContextResponse,
)
from .compact_tasks import execute_compact_context_task
from .game_server_dependencies import CurrentGameServer
from .task_dispatch import defer_room_task

###################################################################################################################################################################
compact_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@compact_api_router.post(
    path="/api/compact_context/v1/", response_model=CompactContextResponse
)
async def compact_context(
    payload: CompactContextRequest,
    game_server: CurrentGameServer,
) -> CompactContextResponse:
    """
    手动上下文压缩接口：压缩指定实体的 LLM 记忆。
    """

    logger.info(
        f"/api/compact_context/v1/: user={payload.user_name} target={payload.target_name}"
    )

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    # 轻量校验：游戏实例存在（激活动作在任务内执行）
    if current_room.game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏，请先登录",
        )

    # 派发 compact pipeline 任务
    job_id = await defer_room_task(
        execute_compact_context_task,
        user_name=payload.user_name,
        target_name=payload.target_name,
    )

    logger.info(f"📝 创建上下文压缩任务: job_id={job_id}, user={payload.user_name}")

    return CompactContextResponse(
        job_id=job_id,
        message="上下文压缩任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
