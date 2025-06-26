from fastapi import APIRouter
from game_services.game_server import GameServerInstance
from models_v_0_0_1 import (
    ViewHomeResponse,
)
from loguru import logger


###################################################################################################################################################################
view_home_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@view_home_router.get(
    path="/view-home/v1/{user_name}/{game_name}", response_model=ViewHomeResponse
)
async def view_home(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
) -> ViewHomeResponse:

    logger.info(f"/view-home/v1/: {user_name}, {game_name}")

    # 是否有房间？！！
    room_manager = game_server.room_manager
    if not room_manager.has_room(user_name):
        logger.error(f"view_home: {user_name} has no room")
        return ViewHomeResponse(
            error=1001,
            message="没有房间",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(user_name)
    assert current_room is not None
    if current_room.game is None:
        logger.error(f"view_home: {user_name} has no game")
        return ViewHomeResponse(
            error=1002,
            message="没有游戏",
        )

    # 获取游戏
    web_game = current_room.game

    # 获取当前地图
    mapping_data = web_game.gen_map()
    logger.info(f"view_home: {user_name} mapping_data: {mapping_data}")

    # 返回。
    return ViewHomeResponse(
        mapping=mapping_data,
        error=0,
        message=f"{mapping_data}",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
