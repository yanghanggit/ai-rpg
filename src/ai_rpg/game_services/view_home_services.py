from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ..game_services.game_server import GameServerInstance
from ..models import (
    ViewHomeResponse,
)

###################################################################################################################################################################
view_home_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@view_home_router.get(
    path="/api/view-home/v1/{user_name}/{game_name}", response_model=ViewHomeResponse
)
async def view_home(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
) -> ViewHomeResponse:

    logger.info(f"/view-home/v1/: {user_name}, {game_name}")
    try:

        # 是否有房间？！！
        # room_manager = game_server.room_manager
        if not game_server.has_room(user_name):
            logger.error(f"view_home: {user_name} has no room")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有房间",
            )

        # 是否有游戏？！！
        current_room = game_server.get_room(user_name)
        assert current_room is not None
        if current_room._game is None:
            logger.error(f"view_home: {user_name} has no game")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏",
            )

        # 获取游戏
        web_game = current_room._game

        # 获取当前地图
        mapping_data = web_game.get_stage_actor_distribution_mapping()
        logger.info(f"view_home: {user_name} mapping_data: {mapping_data}")

        # 返回。
        return ViewHomeResponse(
            mapping=mapping_data,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
