"""副本状态查询服务模块

提供副本状态查询的 API 接口，返回副本中场景与角色的分布情况和副本详细数据。
专门为 TCG 游戏类型设计。
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_dependencies import CurrentGameServer
from ..models import (
    DungeonStateResponse,
)

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
        DungeonStateResponse: 包含场景映射和副本对象的响应

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

    # 获取 TCG 游戏实例
    rpg_game = current_room._tcg_game

    # 获取场景与角色的分布映射
    mapping_data = rpg_game.get_actors_by_stage_as_names()
    logger.info(f"view_dungeon: {user_name} mapping_data: {mapping_data}")

    # 返回副本状态
    return DungeonStateResponse(
        mapping=mapping_data,
        dungeon=rpg_game.current_dungeon,
    )
