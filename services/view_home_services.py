from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models_v_0_0_1 import (
    ViewHomeRequest,
    ViewHomeResponse,
)
from loguru import logger


###################################################################################################################################################################
view_home_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@view_home_router.post(path="/view-home/v1/", response_model=ViewHomeResponse)
async def view_home(
    request_data: ViewHomeRequest,
    game_server: GameServerInstance,
) -> ViewHomeResponse:

    logger.info(f"/view-home/v1/: {request_data.model_dump_json()}")

    # 是否有房间？！！
    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(
            f"home_run: {request_data.user_name} has no room, please login first."
        )
        return ViewHomeResponse(
            error=1001,
            message="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(request_data.user_name)
    assert current_room is not None
    if current_room._game is None:
        logger.error(
            f"home_run: {request_data.user_name} has no game, please login first."
        )
        return ViewHomeResponse(
            error=1002,
            message="没有游戏，请先登录",
        )

    # 判断游戏是否开始
    if not current_room._game.is_game_started:
        logger.error(
            f"home_run: {request_data.user_name} game not started, please start it first."
        )
        return ViewHomeResponse(
            error=1003,
            message="游戏没有开始，请先开始游戏",
        )

    mapping_data = current_room._game.retrieve_stage_actor_names_mapping()
    logger.info(f"home_run: {request_data.user_name} mapping_data: {mapping_data}")

    # 返回。
    return ViewHomeResponse(
        mapping=mapping_data,
        error=0,
        message=f"{mapping_data}",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
