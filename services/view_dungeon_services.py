from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models_v_0_0_1 import (
    ViewDungeonResponse,
)
from loguru import logger


###################################################################################################################################################################
view_dungeon_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@view_dungeon_router.get(
    path="/view-dungeon/v1/{user_name}/{game_name}", response_model=ViewDungeonResponse
)
async def view_dungeon(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
) -> ViewDungeonResponse:

    logger.info(f"/view-dungeon/v1/: {user_name}, {game_name}")

    # 是否有房间？！！
    room_manager = game_server.room_manager
    if not room_manager.has_room(user_name):
        logger.error(f"view_dungeon: {user_name} has no room")
        return ViewDungeonResponse(
            error=1001,
            message="没有房间",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(user_name)
    assert current_room is not None
    if current_room._game is None:
        logger.error(f"view_dungeon: {user_name} has no game")
        return ViewDungeonResponse(
            error=1002,
            message="没有游戏",
        )

    # 获取游戏
    web_game = current_room._game

    # 获取当前地图
    mapping_data = web_game.gen_map()
    logger.info(f"view_dungeon: {user_name} mapping_data: {mapping_data}")

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
