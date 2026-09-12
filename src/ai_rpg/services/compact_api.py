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
from .compact_action import activate_compact_context
from .compact_tasks import execute_compact_context_task
from .game_server_dependencies import CurrentGameServer

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

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 获取游戏实例（不限制场景状态，只要游戏存在即可）
        rpg_game = current_room._dbg_game
        if rpg_game is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏，请先登录",
            )

        # 激活手动压缩动作
        success, error_detail = activate_compact_context(
            rpg_game,
            payload.target_name,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    # 在锁外派发 compact pipeline 任务，让任务独立持锁执行
    deferred_job_id = await execute_compact_context_task.defer_async(
        user_name=payload.user_name
    )
    job_id = deferred_job_id

    logger.info(f"📝 创建上下文压缩任务: job_id={job_id}, user={payload.user_name}")

    return CompactContextResponse(
        job_id=job_id,
        message="上下文压缩任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
