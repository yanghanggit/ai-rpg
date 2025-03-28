from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models.api_models import LoginRequest, LoginResponse
from loguru import logger


login_router = APIRouter()


@login_router.post(path="/login/v1/", response_model=LoginResponse)
async def login(
    request_data: LoginRequest,
    game_server: GameServerInstance,
) -> LoginResponse:

    logger.debug(f"login: {request_data.model_dump_json()}")

    room_manager = game_server.room_manager

    # TODO, 每次都创建新的，有旧的先删除。
    if room_manager.has_room(request_data.user_name):
        pre_room = room_manager.get_room(request_data.user_name)
        assert pre_room is not None
        room_manager.remove_room(pre_room)

    # 创建一个新的房间
    new_room = room_manager.create_room(
        user_name=request_data.user_name,
    )
    assert new_room._game is not None

    # 准备创建一个新的游戏。

    return LoginResponse(
        message="Login successful",
    )
