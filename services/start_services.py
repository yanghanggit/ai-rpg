from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models_v_0_0_1 import StartRequest, StartResponse
from loguru import logger

# TODO, 这里后续会写的复杂一些，从这里开始决定 是继续玩游戏（重连），还是载入再复位然后开始。还是创建一个新游戏？

###################################################################################################################################################################
start_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@start_router.post(path="/start/v1/", response_model=StartResponse)
async def start(
    request_data: StartRequest,
    game_server: GameServerInstance,
) -> StartResponse:

    logger.info(f"start/v1: {request_data.model_dump_json()}")

    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(f"start/v1: {request_data.user_name} not found")
        return StartResponse(
            error=1001,
            message="没有找到房间",
        )

    room = room_manager.get_room(request_data.user_name)
    assert room is not None
    if room._game is None:
        logger.error(f"start/v1: {request_data.user_name} no game")
        return StartResponse(
            error=1002,
            message="没有找到游戏",
        )

    assert room._game is not None
    if room._game.name != request_data.game_name:
        logger.error(f"start/v1: {request_data.user_name} game name not match")
        return StartResponse(
            error=1003,
            message="游戏名称不匹配",
        )

    if room._game.is_game_started:
        logger.error(f"start/v1: {request_data.user_name} game already started")
        return StartResponse(
            error=1004,
            message="游戏已经开始",
        )

    # 这里是启动游戏的逻辑，防止反复启动。
    room._game.is_game_started = True

    # 返回正确的数据。
    return StartResponse(
        error=0,
        message=f"启动游戏成功！!= {';'.join([message.model_dump_json() for message in room._game.player.client_messages])}",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
