"""
副本入口房间 API 路由模块

提供入口房间（叙事 + 牌库生成，无战斗）的初始化接口。
与 combat room API 平级设计，入口房间只需一次 process() 调用完成初始化。
"""

import asyncio
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_dependencies import CurrentGameServer
from ..models import (
    DungeonEntryInitRequest,
    DungeonEntryInitResponse,
    TaskStatus,
)
from .dungeon_lifecycle_api import _validate_dungeon_prerequisites
from .dungeon_entry_tasks import (
    execute_entry_room_init_task,
)

###################################################################################################################################################################
dungeon_entry_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_entry_api_router.post(
    path="/api/dungeon/entry/init/v1/", response_model=DungeonEntryInitResponse
)
async def dungeon_entry_init(
    payload: DungeonEntryInitRequest,
    game_server: CurrentGameServer,
) -> DungeonEntryInitResponse:
    """
    副本入口房间初始化接口
    """

    logger.info(f"/api/dungeon/entry/init/v1/: user={payload.user_name}")

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 验证副本操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 验证当前副本房间是否为入口房间
        if not rpg_game.is_current_room_dungeon_entry:
            logger.error(
                f"玩家 {payload.user_name} 入口房间初始化失败: 当前副本房间不是入口房间"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前副本房间不是入口房间",
            )

        # 状态守护：入口房间已初始化则拒绝重复初始化
        if rpg_game.current_dungeon_entry_room.initialized:
            logger.error(
                f"玩家 {payload.user_name} 入口房间初始化失败: 入口房间已初始化"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="入口房间已初始化",
            )

    # 创建入口房间初始化后台任务（在锁外创建，让任务在后台独立持锁执行）
    entry_init_task = game_server.create_task()
    asyncio.create_task(
        execute_entry_room_init_task(
            entry_init_task.task_id,
            payload.user_name,
            game_server,
        )
    )
    logger.info(
        f"📝 创建入口房间初始化任务: task_id={entry_init_task.task_id}, user={payload.user_name}"
    )

    # 返回入口房间初始化任务启动成功的响应
    return DungeonEntryInitResponse(
        task_id=entry_init_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="入口房间初始化任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
