from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ..game_services.game_server import GameServerInstance
from ..models import (
    ViewDungeonResponse,
)

###################################################################################################################################################################
view_dungeon_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@view_dungeon_router.get(
    path="/api/view-dungeon/v1/{user_name}/{game_name}",
    response_model=ViewDungeonResponse,
)
async def view_dungeon(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
) -> ViewDungeonResponse:

    logger.info(f"/view-dungeon/v1/: {user_name}, {game_name}")
    try:

        # 是否有房间？！！
        room_manager = game_server.room_manager
        if not room_manager.has_room(user_name):
            logger.error(f"view_dungeon: {user_name} has no room")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有房间",
            )

        # 是否有游戏？！！
        current_room = room_manager.get_room(user_name)
        assert current_room is not None
        if current_room.game is None:
            logger.error(f"view_dungeon: {user_name} has no game")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏",
            )

        # 获取游戏
        web_game = current_room.game

        # 获取当前地图
        mapping_data = web_game.get_stage_actor_distribution()
        logger.info(f"view_dungeon: {user_name} mapping_data: {mapping_data}")

        # 返回。
        return ViewDungeonResponse(
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
