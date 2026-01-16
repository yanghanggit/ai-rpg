"""玩家会话消息服务模块

提供玩家会话消息查询的 API 接口，支持从指定序列号开始获取增量消息。
"""

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from ..models import (
    SessionMessageResponse,
)
from .game_server_dependencies import CurrentGameServer

###################################################################################################################################################################
player_session_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
# API增加增量查询端点
@player_session_api_router.get(
    "/api/session_messages/v1/{user_name}/{game_name}/since",
    response_model=SessionMessageResponse,
)
async def get_session_messages(
    game_server: CurrentGameServer,
    user_name: str,
    game_name: str,
    last_sequence_id: int = Query(..., alias="last_sequence_id"),
) -> SessionMessageResponse:
    """增量查询玩家会话消息接口

    从指定的序列号开始获取新的会话消息。

    Args:
        game_server: 游戏服务器实例
        user_name: 用户名
        game_name: 游戏名称
        last_sequence_id: 最后接收到的消息序列号

    Returns:
        SessionMessageResponse: 包含从指定序列号之后的所有新消息

    Raises:
        HTTPException(404): 用户房间或游戏实例不存在
        HTTPException(400): 游戏名称不匹配
    """

    logger.info(
        f"get_session_messages: user_name={user_name}, game_name={game_name}, last_sequence_id={last_sequence_id}"
    )

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        logger.error(f"get_session_messages: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例并检查游戏是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "get_session_messages: room instance is None"

    # 获取 TCG 游戏实例
    rpg_game = current_room._tcg_game
    assert rpg_game is not None, "get_session_messages: TCG game instance is None"
    if rpg_game is None:
        logger.error(f"get_session_messages: {user_name} has no game")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏",
        )

    # 验证游戏名称匹配
    if rpg_game.name != game_name:
        logger.error(f"get_session_messages: {user_name} game_name mismatch")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="游戏名称不匹配",
        )

    # 根据游戏类型获取增量消息
    messages = rpg_game.player_session.get_messages_since(last_sequence_id)
    return SessionMessageResponse(session_messages=messages)
