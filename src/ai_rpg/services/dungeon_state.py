"""副本状态查询服务模块"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_dependencies import CurrentGameServer
from ..models import (
    DungeonStateResponse,
    # DungeonCombatResponse,
    DungeonRoomResponse,
    DungeonListResponse,
    Dungeon,
)
from ..game.config import DUNGEONS_DIR

###################################################################################################################################################################
dungeon_state_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_state_api_router.get(
    path="/api/dungeons/v1/{user_name}/{game_name}/state",
    response_model=DungeonStateResponse,
)
async def get_dungeon_state(
    game_server: CurrentGameServer,
    user_name: str,
    game_name: str,
) -> DungeonStateResponse:
    """查询副本状态接口"""

    logger.info(f"/dungeons/v1/{user_name}/{game_name}/state: {user_name}, {game_name}")

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        logger.error(f"view_dungeon: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例并检查 DBG 游戏是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "get_dungeon_state: room instance is None"
    if current_room._dbg_game is None:
        logger.error(f"view_dungeon: {user_name} has no game")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏",
        )

    # 返回副本状态
    return DungeonStateResponse(
        dungeon=current_room._dbg_game.current_dungeon,
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_state_api_router.get(
    path="/api/dungeons/v1/{user_name}/{game_name}/room",
    response_model=DungeonRoomResponse,
)
async def get_dungeon_room(
    game_server: CurrentGameServer,
    user_name: str,
    game_name: str,
) -> DungeonRoomResponse:
    """查询当前副本房间接口"""

    logger.info(f"/dungeons/v1/{user_name}/{game_name}/room: {user_name}, {game_name}")

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        logger.error(f"get_dungeon_room: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例并检查 DBG 游戏是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "get_dungeon_room: room instance is None"
    if current_room._dbg_game is None:
        logger.error(f"get_dungeon_room: {user_name} has no game")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏",
        )

    # 获取当前副本房间，current_room_index == -1 或超出范围时返回 None
    current_dungeon_room = current_room._dbg_game.current_dungeon.current_room
    if current_dungeon_room is None:
        logger.error(f"get_dungeon_room: {user_name} has no current dungeon room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="当前副本没有进行中的房间",
        )

    # 返回当前副本房间的响应对象，包含房间的关卡场景（若是战斗房间则包含战斗数据）
    return DungeonRoomResponse(room=current_dungeon_room)


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_state_api_router.get(
    path="/api/home/dungeon-list/v1/", response_model=DungeonListResponse
)
async def list_dungeons() -> DungeonListResponse:
    """获取可用副本列表接口"""
    dungeons = sorted(
        (
            Dungeon.model_validate_json(p.read_text(encoding="utf-8"))
            for p in DUNGEONS_DIR.glob("*.json")
        ),
        key=lambda d: d.created_at,
    )
    return DungeonListResponse(dungeons=dungeons)


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
