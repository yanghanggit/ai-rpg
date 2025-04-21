from fastapi import APIRouter
from game.web_tcg_game import WebTCGGame
from services.game_server_instance import GameServerInstance
from models_v_0_0_1 import (
    ViewDungeonRequest,
    ViewDungeonResponse,
)
from loguru import logger


###################################################################################################################################################################
view_dungeon_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@view_dungeon_router.post(path="/view-dungeon/v1/", response_model=ViewDungeonResponse)
async def view_dungeon(
    request_data: ViewDungeonRequest,
    game_server: GameServerInstance,
) -> ViewDungeonResponse:

    logger.info(f"/view-dungeon/v1/: {request_data.model_dump_json()}")

    # 是否有房间？！！
    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(
            f"view_dungeon: {request_data.user_name} has no room, please login first."
        )
        return ViewDungeonResponse(
            error=1001,
            message="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(request_data.user_name)
    assert current_room is not None
    if current_room._game is None:
        logger.error(
            f"view_dungeon: {request_data.user_name} has no game, please login first."
        )
        return ViewDungeonResponse(
            error=1002,
            message="没有游戏，请先登录",
        )

    web_game = current_room._game
    assert web_game is not None
    assert isinstance(web_game, WebTCGGame)

    # 判断游戏是否开始
    if not web_game.is_game_started:
        logger.error(
            f"view_dungeon: {request_data.user_name} game not started, please start it first."
        )
        return ViewDungeonResponse(
            error=1003,
            message="游戏没有开始，请先开始游戏",
        )

    mapping_data = web_game.gen_map()
    logger.info(f"view_dungeon: {request_data.user_name} mapping_data: {mapping_data}")

    # 返回。
    return ViewDungeonResponse(
        mapping=mapping_data,
        dungeon=web_game.current_dungeon,
        error=0,
        message=web_game.current_dungeon.model_dump_json(),
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
