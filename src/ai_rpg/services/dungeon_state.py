"""副本状态查询服务模块

提供副本状态查询的 API 接口，返回副本状态、当前战斗及当前房间等详细数据。
专门为 TCG 游戏类型设计。
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_dependencies import CurrentGameServer
from ..models import (
    DungeonStateResponse,
    DungeonCombatResponse,
    DungeonRoomResponse,
    DungeonListResponse,
    Dungeon,
    CombatRoom,
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
    """查询副本状态接口

    查询 TCG 游戏中当前副本的状态信息，包括场景与角色的分布映射和副本数据。

    Args:
        game_server: 游戏服务器实例
        user_name: 用户名
        game_name: 游戏名称

    Returns:
        DungeonStateResponse: 包含副本对象的响应

    Raises:
        HTTPException(404): 用户房间或游戏实例不存在
    """

    logger.info(f"/dungeons/v1/{user_name}/{game_name}/state: {user_name}, {game_name}")

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        logger.error(f"view_dungeon: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例并检查 TCG 游戏是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "get_dungeon_state: room instance is None"
    if current_room._tcg_game is None:
        logger.error(f"view_dungeon: {user_name} has no game")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏",
        )

    # 返回副本状态
    return DungeonStateResponse(
        dungeon=current_room._tcg_game.current_dungeon,
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_state_api_router.get(
    path="/api/dungeons/v1/{user_name}/{game_name}/combat",
    response_model=DungeonCombatResponse,
)
async def get_dungeon_combat(
    game_server: CurrentGameServer,
    user_name: str,
    game_name: str,
) -> DungeonCombatResponse:
    """查询副本战斗状态接口

    查询 TCG 游戏中当前副本的战斗状态信息，包括当前战斗对象。

    Args:
        game_server: 游戏服务器实例
        user_name: 用户名
        game_name: 游戏名称

    Returns:
        DungeonCombatResponse: 包含当前战斗对象的响应

    Raises:
        HTTPException(404): 用户房间或游戏实例不存在
    """

    logger.info(
        f"/dungeons/v1/{user_name}/{game_name}/combat: {user_name}, {game_name}"
    )

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        logger.error(f"get_dungeon_combat: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例并检查 TCG 游戏是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "get_dungeon_combat: room instance is None"
    if current_room._tcg_game is None:
        logger.error(f"get_dungeon_combat: {user_name} has no game")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏",
        )

    # 获取当前战斗，不应该出现没有战斗的情况，因为只有在战斗阶段才会调用这个接口，但为了安全起见，还是加个检查
    current_combat = current_room._tcg_game.current_dungeon.current_combat
    assert current_combat is not None, "当前地下城没有进行中的战斗"
    if current_combat is None:
        logger.error(f"get_dungeon_combat: {user_name} has no current combat")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有进行中的战斗",
        )

    # 返回当前战斗状态
    return DungeonCombatResponse(combat=current_combat)


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
    """查询当前地下城房间接口

    查询 TCG 游戏中当前地下城所在的房间信息，包括关卡场景与战斗数据。

    Args:
        game_server: 游戏服务器实例
        user_name: 用户名
        game_name: 游戏名称

    Returns:
        DungeonRoomResponse: 包含当前房间对象（stage + combat）的响应

    Raises:
        HTTPException(404): 用户房间或游戏实例不存在，或地下城尚未进入任何房间
    """

    logger.info(f"/dungeons/v1/{user_name}/{game_name}/room: {user_name}, {game_name}")

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        logger.error(f"get_dungeon_room: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例并检查 TCG 游戏是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "get_dungeon_room: room instance is None"
    if current_room._tcg_game is None:
        logger.error(f"get_dungeon_room: {user_name} has no game")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏",
        )

    # 获取当前地下城房间，current_room_index == -1 或超出范围时返回 None
    current_dungeon_room = current_room._tcg_game.current_dungeon.current_room
    if current_dungeon_room is None:
        logger.error(f"get_dungeon_room: {user_name} has no current dungeon room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="当前地下城没有进行中的房间",
        )

    # 返回当前房间
    if not isinstance(current_dungeon_room, CombatRoom):
        logger.error(f"get_dungeon_room: {user_name} current room is not a CombatRoom")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="当前房间不是战斗房间",
        )
    return DungeonRoomResponse(room=current_dungeon_room)


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_state_api_router.get(
    path="/api/home/dungeon-list/v1/", response_model=DungeonListResponse
)
async def list_dungeons() -> DungeonListResponse:
    """获取可用地下城列表接口

    遍历 DUNGEONS_DIR 目录下的所有 JSON 文件，读取并返回其内容，供客户端预览选择。

    Returns:
        DungeonListResponse: 包含所有地下城配置的列表响应
    """
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
