"""
副本奖励（Spoils）API 路由模块。

提供非战斗房间的奖励生成（GenerateSpoilsAction）、领卡（PickSpoilsAction 子操作 pick_card）
与奖励清理接口。奖励隶属于「非战斗房间」，与具体房间类型（开场房 / 未来的其它非战斗房）解耦。
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ..models import (
    DungeonSpoilsGenerateRequest,
    DungeonSpoilsGenerateResponse,
    DungeonSpoilsPickCardRequest,
    DungeonSpoilsPickCardResponse,
    DungeonSpoilsRemoveRequest,
    DungeonSpoilsRemoveResponse,
)
from .dungeon_lifecycle_api import _validate_dungeon_prerequisites
from .dungeon_spoils_actions import remove_spoils
from .dungeon_spoils_tasks import (
    execute_generate_spoils_task,
    execute_pick_spoils_card_task,
)
from .game_server_dependencies import CurrentGameServer
from .task_dispatch import defer_room_task

###################################################################################################################################################################
dungeon_spoils_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_spoils_api_router.post(
    path="/api/dungeon/spoils/generate/v1/",
    response_model=DungeonSpoilsGenerateResponse,
)
async def dungeon_spoils_generate(
    payload: DungeonSpoilsGenerateRequest,
    game_server: CurrentGameServer,
) -> DungeonSpoilsGenerateResponse:
    """
    副本奖励生成接口（外部显式触发 GenerateSpoilsAction）
    """

    logger.info(f"/api/dungeon/spoils/generate/v1/: user={payload.user_name}")

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

    # 验证当前副本房间为非战斗房间（奖励隶属于非战斗房间）
    if rpg_game.is_current_room_dungeon_combat:
        logger.error(f"玩家 {payload.user_name} 奖励生成失败: 当前副本房间是战斗房间")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前副本房间是战斗房间",
        )

    # 派发奖励生成任务
    job_id = await defer_room_task(
        execute_generate_spoils_task, user_name=payload.user_name
    )
    logger.info(f"📝 创建奖励生成任务: job_id={job_id}, user={payload.user_name}")

    # 返回奖励生成任务启动成功的响应
    return DungeonSpoilsGenerateResponse(
        job_id=job_id,
        message="奖励生成任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_spoils_api_router.post(
    path="/api/dungeon/spoils/pick_card/v1/",
    response_model=DungeonSpoilsPickCardResponse,
)
async def dungeon_spoils_pick_card(
    payload: DungeonSpoilsPickCardRequest,
    game_server: CurrentGameServer,
) -> DungeonSpoilsPickCardResponse:
    """
    副本领卡接口（Spoils 子操作：pick_card；外部显式触发 PickSpoilsAction）
    """

    logger.info(
        f"/api/dungeon/spoils/pick_card/v1/: user={payload.user_name} "
        f"actor={payload.actor_name} card={payload.card_name}"
    )

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

    # 验证当前副本房间为非战斗房间
    if rpg_game.is_current_room_dungeon_combat:
        logger.error(f"玩家 {payload.user_name} 领卡失败: 当前副本房间是战斗房间")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前副本房间是战斗房间",
        )

    # 派发领卡任务
    job_id = await defer_room_task(
        execute_pick_spoils_card_task,
        user_name=payload.user_name,
        actor_name=payload.actor_name,
        card_name=payload.card_name,
    )
    logger.info(f"📝 创建领卡任务: job_id={job_id}, user={payload.user_name}")

    # 返回领卡任务启动成功的响应
    return DungeonSpoilsPickCardResponse(
        job_id=job_id,
        message="领卡任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_spoils_api_router.post(
    path="/api/dungeon/spoils/remove/v1/",
    response_model=DungeonSpoilsRemoveResponse,
)
async def dungeon_spoils_remove(
    payload: DungeonSpoilsRemoveRequest,
    game_server: CurrentGameServer,
) -> DungeonSpoilsRemoveResponse:
    """
    清理当前副本队伍成员的奖励状态（SpoilsComponent）。
    """

    logger.info(f"/api/dungeon/spoils/remove/v1/: user={payload.user_name}")

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room.transaction():

        # 验证副本操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        success, message = remove_spoils(rpg_game)
        if not success:
            logger.error(f"玩家 {payload.user_name} 清理奖励失败: {message}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=message,
            )

        return DungeonSpoilsRemoveResponse(message=message)
