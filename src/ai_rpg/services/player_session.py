from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from ..models import (
    SessionMessageResponse,
)
from .game_server_depends import GameServerInstance

###################################################################################################################################################################
player_session_api_router = APIRouter()


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

    logger.info(
        f"get_session_messages: user_name={user_name}, game_name={game_name}, last_sequence_id={last_sequence_id}"
    )

    try:

        # 是否有房间？！！
        if not game_server.has_room(user_name):
            logger.error(f"get_session_messages: {user_name} has no room")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有房间",
            )

        # 是否有游戏？！！
        current_room = game_server.get_room(user_name)
        assert current_room is not None
        if current_room._sdg_game is None and current_room._tcg_game is None:
            logger.error(f"get_session_messages: {user_name} has no game")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏",
            )

        # 获取增量消息
        if (
            current_room._sdg_game is not None
            and game_name == current_room._sdg_game.name
        ):
            # game_name == current_room._sdg_game.name:
            assert current_room._sdg_game is not None, "SDGGame should not be None"
            messages = current_room._sdg_game.player_session.get_messages_since(
                last_sequence_id
            )
        elif (
            current_room._tcg_game is not None
            and game_name == current_room._tcg_game.name
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

    except Exception as e:
        logger.error(f"get_session_messages: {user_name} error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}",
        )

    return SessionMessageResponse(session_messages=[])
