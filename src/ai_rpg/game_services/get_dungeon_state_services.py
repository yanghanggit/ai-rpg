from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server import GameServerInstance
from ..models import (
    DungeonStateResponse,
)

###################################################################################################################################################################
get_dungeon_state_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@get_dungeon_state_api_router.get(
    path="/api/dungeons/v1/{user_name}/{game_name}/state",
    response_model=DungeonStateResponse,
)
async def get_dungeon_state(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
) -> DungeonStateResponse:

    logger.info(f"/dungeons/v1/{user_name}/{game_name}/state: {user_name}, {game_name}")
    try:

        # 是否有房间？！！
        # room_manager = game_server.room_manager
        if not game_server.has_room(user_name):
            logger.error(f"view_dungeon: {user_name} has no room")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有房间",
            )

        # 是否有游戏？！！
        current_room = game_server.get_room(user_name)
        assert current_room is not None
        if current_room._game is None:
            logger.error(f"view_dungeon: {user_name} has no game")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏",
            )

        # 获取游戏
        web_game = current_room._game

        # 获取当前地图
        mapping_data = web_game.get_stage_actor_distribution_mapping()
        logger.info(f"view_dungeon: {user_name} mapping_data: {mapping_data}")

        # 返回。
        return DungeonStateResponse(
            mapping=mapping_data,
            dungeon=web_game.current_dungeon,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
