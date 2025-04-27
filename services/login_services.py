from enum import StrEnum, unique
import os
from typing import Final, final
from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models_v_0_0_1 import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
)
from loguru import logger
from game.startup_options import WebUserSessionOptions
from game.tcg_game_demo import (
    create_then_write_demo_world,
)
import shutil
from fastapi.staticfiles import StaticFiles
from game.tcg_game_config import GEN_RUNTIME_DIR

###################################################################################################################################################################
login_router = APIRouter()
###################################################################################################################################################################
ENFORCE_NEW_GAME: Final[bool] = True


###################################################################################################################################################################
@final
@unique
class GameSessionStatus(StrEnum):
    RESUME_GAME = "resume_game"
    LOAD_GAME = "load_game"
    NEW_GAME = "new_game"


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@login_router.post(path="/login/v1/", response_model=LoginResponse)
async def login(
    request_data: LoginRequest,
    game_server: GameServerInstance,
) -> LoginResponse:

    logger.info(f"login/v1: {request_data.model_dump_json()}")

    # 转化成复杂参数
    web_user_session_options = WebUserSessionOptions(
        user=request_data.user_name,
        game=request_data.game_name,
        actor="",
    )

    # 初始化日志
    web_user_session_options.setup_logger()

    # 检查房间是否存在
    room_manager = game_server.room_manager

    # TODO, 强制新游戏
    if ENFORCE_NEW_GAME:

        # TODO, 强制删除运行中的房间。
        if room_manager.has_room(request_data.user_name):
            pre_room = room_manager.get_room(request_data.user_name)
            assert pre_room is not None
            logger.info(
                f"login: {request_data.user_name} has room, remove it = {pre_room._user_name}"
            )
            room_manager.remove_room(pre_room)

        # TODO, 这里需要设置一个新的目录，清除旧的目录。
        web_user_session_options.clear_runtime_dir()

        # TODO, 临时创建一个
        demo_world_setup = create_then_write_demo_world(
            web_user_session_options.game, web_user_session_options.gen_world_boot_file
        )
        assert demo_world_setup is not None

        # TODO, 游戏资源可以被创建，将gen_world_boot_file这个文件拷贝一份到world_runtime_dir下
        shutil.copy(
            web_user_session_options.gen_world_boot_file,
            web_user_session_options.world_runtime_dir,
        )

    # TODO, get测试。
    # 指向包含 runtime.json 的目录。
    static_dir = os.path.join(
        GEN_RUNTIME_DIR, web_user_session_options.user, web_user_session_options.game
    )
    # 将该目录挂载到 "/files" 路径上
    game_server.fast_api.mount(
        "/files", StaticFiles(directory=static_dir), name="files"
    )
    # 如果能开启就用get方法测试
    # http://127.0.0.1:8000/files/runtime.json
    # http://局域网地址:8000/files/runtime.json

    # 登录成功就开个房间。
    if not room_manager.has_room(request_data.user_name):
        logger.info(f"start/v1: {request_data.user_name} not found, create room")
        new_room = room_manager.create_room(
            user_name=request_data.user_name,
        )
        logger.info(
            f"login: {request_data.user_name} create room = {new_room._user_name}"
        )
        assert new_room._game is None

    # 如果有房间，就获取房间。
    room = room_manager.get_room(request_data.user_name)
    assert room is not None

    # 返回结果。
    response_message = ""
    if room._game is not None:
        # 存在，正在运行
        logger.info(f"login: {request_data.user_name} has room, is running!")
        response_message = GameSessionStatus.RESUME_GAME
    else:
        if web_user_session_options.world_runtime_file.exists():
            # 曾经运行过，此时已经存储，可以恢复
            logger.info(
                f"login: {request_data.user_name} has room, but not running, can restore!"
            )
            response_message = GameSessionStatus.LOAD_GAME
        else:
            # 没有运行过，直接创建
            logger.info(
                f"login: {request_data.user_name} has room, but not running, create new room!"
            )
            response_message = GameSessionStatus.NEW_GAME

    return LoginResponse(
        error=0,
        message=response_message,
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@login_router.post(path="/logout/v1/", response_model=LogoutResponse)
async def logout(
    request_data: LogoutRequest,
    game_server: GameServerInstance,
) -> LogoutResponse:

    logger.info(f"logout: {request_data.model_dump_json()}")

    # 先检查房间是否存在
    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(f"logout: {request_data.user_name} not found")
        return LogoutResponse(
            error=1001,
            message="没有找到房间",
        )

    # 删除房间
    pre_room = room_manager.get_room(request_data.user_name)
    assert pre_room is not None
    if pre_room._game is not None:
        # 保存游戏的运行时数据
        logger.info(
            f"logout: {request_data.user_name} save game = {pre_room._game.name}"
        )
        pre_room._game.save()
        # 退出游戏
        logger.info(
            f"logout: {request_data.user_name} exit game = {pre_room._game.name}"
        )
        # 退出游戏
        pre_room._game.exit()

    else:
        logger.info(f"logout: {request_data.user_name} no game = {pre_room._user_name}")

    logger.info(f"logout: {request_data.user_name} remove room = {pre_room._user_name}")
    room_manager.remove_room(pre_room)
    return LogoutResponse(
        error=0,
        message=f"logout: {request_data.user_name} success",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
