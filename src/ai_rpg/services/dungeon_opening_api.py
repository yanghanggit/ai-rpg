"""
副本开场房间 API 路由模块

提供开场房间（叙事 + 牌库初始化，无战斗）的初始化接口，
以及卡池生成（GenerateCardPoolAction，外部显式触发）接口。
与 combat room API 平级设计，开场房间只需一次 process() 调用完成初始化。
"""

import asyncio
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_dependencies import CurrentGameServer
from ..models import (
    DungeonOpeningGenerateCardPoolRequest,
    DungeonOpeningGenerateCardPoolResponse,
    DungeonOpeningInitRequest,
    DungeonOpeningInitResponse,
    TaskStatus,
)
from .dungeon_lifecycle_api import _validate_dungeon_prerequisites
from .dungeon_opening_tasks import (
    execute_generate_card_pool_task,
    execute_opening_room_init_task,
)

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

        # 验证当前副本房间是否为开场房间
        if not rpg_game.is_current_room_dungeon_opening:
            logger.error(
                f"玩家 {payload.user_name} 开场房间初始化失败: 当前副本房间不是开场房间"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前副本房间不是开场房间",
            )

        # 状态守护：开场房间已初始化则拒绝重复初始化
        if rpg_game.current_dungeon_opening_room.initialized:
            logger.error(
                f"玩家 {payload.user_name} 开场房间初始化失败: 开场房间已初始化"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="开场房间已初始化",
            )

    # 创建开场房间初始化后台任务（在锁外创建，让任务在后台独立持锁执行）
    opening_init_task = game_server.create_task()
    asyncio.create_task(
        execute_opening_room_init_task(
            opening_init_task.task_id,
            payload.user_name,
            game_server,
        )
    )
    logger.info(
        f"📝 创建开场房间初始化任务: task_id={opening_init_task.task_id}, user={payload.user_name}"
    )

    # 返回开场房间初始化任务启动成功的响应
    return DungeonOpeningInitResponse(
        task_id=opening_init_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="开场房间初始化任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_opening_api_router.post(
    path="/api/dungeon/opening/generate_card_pool/v1/",
    response_model=DungeonOpeningGenerateCardPoolResponse,
)
async def dungeon_opening_generate_card_pool(
    payload: DungeonOpeningGenerateCardPoolRequest,
    game_server: CurrentGameServer,
) -> DungeonOpeningGenerateCardPoolResponse:
    """
    副本开场房间卡池生成接口（外部显式触发 GenerateCardPoolAction）
    """

    logger.info(
        f"/api/dungeon/opening/generate_card_pool/v1/: user={payload.user_name}"
    )

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

        # 验证当前副本房间是否为开场房间
        if not rpg_game.is_current_room_dungeon_opening:
            logger.error(
                f"玩家 {payload.user_name} 卡池生成失败: 当前副本房间不是开场房间"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前副本房间不是开场房间",
            )

        # 状态守护：卡池生成依赖开场初始化（叙事 + 牌库）已完成
        if not rpg_game.current_dungeon_opening_room.initialized:
            logger.error(f"玩家 {payload.user_name} 卡池生成失败: 开场房间尚未初始化")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="开场房间尚未初始化（叙事 + 牌库），请先调用开场初始化接口",
            )

    # 创建卡池生成后台任务（在锁外创建，让任务在后台独立持锁执行）
    generate_card_pool_task = game_server.create_task()
    asyncio.create_task(
        execute_generate_card_pool_task(
            generate_card_pool_task.task_id,
            payload.user_name,
            game_server,
        )
    )
    logger.info(
        f"📝 创建卡池生成任务: task_id={generate_card_pool_task.task_id}, user={payload.user_name}"
    )

    # 返回卡池生成任务启动成功的响应
    return DungeonOpeningGenerateCardPoolResponse(
        task_id=generate_card_pool_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="卡池生成任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
