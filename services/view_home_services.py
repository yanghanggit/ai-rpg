from fastapi import APIRouter
from game.web_tcg_game import WebTCGGame
from services.game_server_instance import GameServerInstance
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
        logger.error(f"view_home: {user_name} has no room, please login first.")
        return ViewHomeResponse(
            error=1001,
            message="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(user_name)
    assert current_room is not None
    if current_room._game is None:
        logger.error(f"view_home: {user_name} has no game, please login first.")
        return ViewHomeResponse(
            error=1002,
            message="没有游戏，请先登录",
        )

    web_game = current_room._game
    assert web_game.name == game_name
    assert web_game is not None
    assert isinstance(web_game, WebTCGGame)

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
