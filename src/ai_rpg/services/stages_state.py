"""场景状态查询服务模块

提供场景状态查询的 API 接口，返回游戏中所有场景及其角色分布情况。
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_dependencies import CurrentGameServer
from ..models import (
    StagesStateResponse,
)

###################################################################################################################################################################
stages_state_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@stages_state_api_router.get(
    path="/api/stages/v1/{user_name}/{game_name}/state",
    response_model=StagesStateResponse,
)
async def get_stages_state(
    game_server: CurrentGameServer,
    user_name: str,
    game_name: str,
) -> StagesStateResponse:
    """查询场景状态接口

    查询游戏中所有场景的状态信息，包括场景与角色的分布映射关系。

    Args:
        game_server: 游戏服务器实例
        user_name: 用户名
        game_name: 游戏名称

    Returns:
        StagesStateResponse: 包含场景与角色映射关系的响应

    Raises:
        HTTPException(404): 用户房间不存在
        HTTPException(400): 游戏名称不匹配
    """

    logger.info(f"get_stages_state: {user_name}, {game_name}")

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        logger.error(f"view_home: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "get_stages_state: room instance is None"

    # 根据游戏类型获取游戏实例
    rpg_game = current_room._tcg_game
    assert rpg_game is not None, "WebGame should not be None"
    if rpg_game is None:
        logger.error(f"get_stages_messages: {user_name} has no RPG game")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有RPG游戏",
        )

    # 验证游戏名称匹配
    if rpg_game.name != game_name:
        logger.error(f"get_stages_messages: {user_name} game_name mismatch")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="游戏名称不匹配",
        )

    # 获取场景与角色的分布映射
    actors_by_stage_as_names = rpg_game.get_actors_by_stage_as_names()
    logger.info(f"view_home: {user_name} mapping_data: {actors_by_stage_as_names}")

    # 返回场景状态
    return StagesStateResponse(
        mapping=actors_by_stage_as_names,
    )
