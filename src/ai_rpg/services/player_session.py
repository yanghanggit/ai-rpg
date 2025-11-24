"""玩家会话消息服务模块

本模块提供玩家会话消息查询的 API 接口，主要功能包括：
- 增量查询玩家会话消息，支持从指定序列号开始获取新消息
- 支持多种游戏类型（SDG 和 TCG 游戏）的消息查询
- 验证用户房间和游戏实例的存在性

消息查询流程：
1. 验证用户房间是否存在
2. 验证游戏实例是否存在
3. 根据游戏类型（SDG 或 TCG）获取对应的消息
4. 从指定的序列号开始返回增量消息

注意事项：
- 必须先创建房间并启动游戏才能查询消息
- 支持 SDG 游戏和 TCG 游戏两种类型
- 游戏名称必须与当前运行的游戏匹配
- 使用增量查询可以有效减少数据传输量
- 所有异常由 FastAPI 框架统一处理，确保客户端收到正确的 HTTP 状态码
"""

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from ..models import (
    SessionMessageResponse,
)
from .game_server_depends import GameServerInstance

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
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
    last_sequence_id: int = Query(..., alias="last_sequence_id"),
) -> SessionMessageResponse:
    """增量查询玩家会话消息接口

    提供增量查询功能，从指定的序列号开始获取新的会话消息。
    支持 SDG 和 TCG 两种游戏类型，根据游戏类型自动路由到对应的消息源。

    Args:
        game_server: 游戏服务器实例，管理所有用户房间和游戏会话
        user_name: 用户名，用于定位用户房间
        game_name: 游戏名称，用于匹配当前运行的游戏
        last_sequence_id: 最后接收到的消息序列号，查询此序列号之后的新消息

    Returns:
        SessionMessageResponse: 会话消息响应，包含从指定序列号之后的所有新消息列表

    Raises:
        HTTPException(404): 以下情况会返回 404 错误：
            - 用户房间不存在，需要先调用 login 接口
            - 游戏实例不存在，需要先调用 start 接口
        HTTPException(400): 游戏名称与当前运行的游戏不匹配
        AssertionError: 当关键对象状态异常时抛出

    Note:
        - 必须先调用 /api/login/v1/ 创建房间
        - 必须先调用 /api/start/v1/ 或狼人杀启动接口启动游戏
        - 支持 SDG 游戏（_sdg_game）和 TCG 游戏（_tcg_game）
        - 游戏名称必须与房间中当前运行的游戏名称完全匹配
        - 使用 last_sequence_id 参数实现增量查询，避免重复获取已处理的消息
        - 客户端应保存最后收到的消息序列号，用于下次查询
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
    if current_room._sdg_game is None and current_room._tcg_game is None:
        logger.error(f"get_session_messages: {user_name} has no game")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏",
        )

    # 根据游戏类型获取增量消息
    if current_room._sdg_game is not None and game_name == current_room._sdg_game.name:
        assert current_room._sdg_game is not None, "SDGGame should not be None"
        messages = current_room._sdg_game.player_session.get_messages_since(
            last_sequence_id
        )
    elif (
        current_room._tcg_game is not None and game_name == current_room._tcg_game.name
    ):
        assert current_room._tcg_game is not None, "TCGGame should not be None"
        messages = current_room._tcg_game.player_session.get_messages_since(
            last_sequence_id
        )
    else:
        logger.error(f"get_session_messages: {user_name} game_name mismatch")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="游戏名称不匹配",
        )

    return SessionMessageResponse(session_messages=messages)
