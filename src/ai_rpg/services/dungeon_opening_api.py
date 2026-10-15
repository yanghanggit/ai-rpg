"""
副本开场房间 API 路由模块

提供开场房间的初始化接口（叙事 + 环境初始化，无战斗）。
奖励（Spoils）相关接口已迁至 dungeon_spoils_api.py，与开场房间解耦。
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ..models import (
    DungeonOpeningInitRequest,
    DungeonOpeningInitResponse,
)
from .dungeon_lifecycle_api import _validate_dungeon_prerequisites
from .dungeon_opening_tasks import execute_opening_room_init_task
from .game_server_dependencies import CurrentGameServer
from .task_dispatch import defer_room_task

###################################################################################################################################################################
dungeon_opening_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_opening_api_router.post(
    path="/api/dungeon/opening/init/v1/", response_model=DungeonOpeningInitResponse
)
async def dungeon_opening_init(
    payload: DungeonOpeningInitRequest,
    game_server: CurrentGameServer,
) -> DungeonOpeningInitResponse:
    """
    副本开场房间初始化接口
    """

    logger.info(f"/api/dungeon/opening/init/v1/: user={payload.user_name}")

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    # 验证副本操作的前置条件
    rpg_game = _validate_dungeon_prerequisites(
        user_name=payload.user_name,
        game_server=game_server,
    )

    # 验证当前副本房间是否为开场房间
    if not rpg_game.is_current_room_dungeon_opening:
        logger.error(
            f"玩家 {payload.user_name} 开场房间初始化失败: 当前副本房间不是开场房间"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前副本房间不是开场房间",
        )

    # 开场初始化管道内部按消息标记幂等，可安全重复调用，无需额外状态位守护。
    # 派发开场房间初始化任务
    job_id = await defer_room_task(
        execute_opening_room_init_task, user_name=payload.user_name
    )
    logger.info(f"📝 创建开场房间初始化任务: job_id={job_id}, user={payload.user_name}")

    # 返回开场房间初始化任务启动成功的响应
    return DungeonOpeningInitResponse(
        job_id=job_id,
        message="开场房间初始化任务已启动，请通过会话消息查询结果",
    )
