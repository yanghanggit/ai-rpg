from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.web_tcg_game import WebGameSessionContext
from ..game_services.game_server import GameServerInstance
from ..models import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
)

###################################################################################################################################################################
login_router = APIRouter()
###################################################################################################################################################################


###################################################################################################################################################################
# @final
# @unique
# class GameSessionStatus(StrEnum):
#     RESUME_GAME = "resume_game"
#     LOAD_GAME = "load_game"
#     NEW_GAME = "new_game"


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@login_router.post(path="/api/login/v1/", response_model=LoginResponse)
async def login(
    request_data: LoginRequest,
    game_server: GameServerInstance,
    # request: Request,  # 新增
) -> LoginResponse:

    logger.info(f"/login/v1/: {request_data.model_dump_json()}")

    # 转化成复杂参数
    game_session_context = WebGameSessionContext(
        user=request_data.user_name,
        game=request_data.game_name,
        actor="",
    )

    # 初始化日志
    # setup_logger()

    # 检查房间是否存在
    room_manager = game_server.room_manager

    # TODO, 强制删除运行中的房间。
    if room_manager.has_room(request_data.user_name):
        logger.debug(f"这是测试，强制删除旧房间 = {request_data.user_name}")
        pre_room = room_manager.get_room(request_data.user_name)
        assert pre_room is not None
        logger.info(
            f"login: {request_data.user_name} has room, remove it = {pre_room._user_name}"
        )
        room_manager.remove_room(pre_room)

    # TODO, 这里需要设置一个新的目录，清除旧的目录。
    logger.debug(
        f"这是测试，强制删除旧的游戏数据 = {game_session_context.user}, {game_session_context.game}"
    )
    game_session_context.delete_world_data()

    # TODO, get测试。
    # 指向包含 runtime.json 的目录。
    # fastapi_app: FastAPI = request.app
    # static_dir = LOGS_DIR / web_game_user_options.user / web_game_user_options.game
    # if not static_dir.exists():
    #     static_dir.mkdir(parents=True, exist_ok=True)
    # # 将该目录挂载到 "/files" 路径上
    # fastapi_app.mount("/files", StaticFiles(directory=static_dir), name="files")
    # 如果能开启就用get方法测试
    # http://127.0.0.1:8000/files/runtime.json
    # http://局域网地址:8000/files/runtime.json

    # 登录成功就开个空的房间!
    if not room_manager.has_room(request_data.user_name):
        logger.info(f"start/v1: {request_data.user_name} not found, create room")
        new_room = room_manager.create_room(
            user_name=request_data.user_name,
        )
        logger.info(
            f"login: {request_data.user_name} create room = {new_room._user_name}"
        )
        assert new_room.game is None

    # 如果有房间，就获取房间。
    room = room_manager.get_room(request_data.user_name)
    assert room is not None

    # 返回结果。
    # response_message = ""
    # if room.game is not None:
    #     # 存在，正在运行
    #     logger.info(f"login: {request_data.user_name} has room, is running!")
    #     response_message = GameSessionStatus.RESUME_GAME
    # else:
    #     if web_game_user_options.world_data is not None:
    #         # 曾经运行过，此时已经存储，可以恢复
    #         logger.info(
    #             f"login: {request_data.user_name} has room, but not running, can restore!"
    #         )
    #         response_message = GameSessionStatus.LOAD_GAME
    #     else:
    #         # 没有运行过，直接创建
    #         logger.info(
    #             f"login: {request_data.user_name} has room, but not running, create new room!"
    #         )
    #         response_message = GameSessionStatus.NEW_GAME

    return LoginResponse(
        message=f"{request_data.user_name} 登录成功！并创建房间！",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@login_router.post(path="/api/logout/v1/", response_model=LogoutResponse)
async def logout(
    request_data: LogoutRequest,
    game_server: GameServerInstance,
) -> LogoutResponse:

    logger.info(f"/logout/v1/: {request_data.model_dump_json()}")

    try:

        # 先检查房间是否存在
        room_manager = game_server.room_manager
        if not room_manager.has_room(request_data.user_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"logout: {request_data.user_name} not found",
            )

        # 删除房间
        pre_room = room_manager.get_room(request_data.user_name)
        assert pre_room is not None
        if pre_room.game is not None:
            # 保存游戏的运行时数据
            logger.info(
                f"logout: {request_data.user_name} save game = {pre_room.game.name}"
            )
            pre_room.game.save()
            # 退出游戏
            logger.info(
                f"logout: {request_data.user_name} exit game = {pre_room.game.name}"
            )
            # 退出游戏
            pre_room.game.exit()

        else:
            logger.info(
                f"logout: {request_data.user_name} no game = {pre_room._user_name}"
            )

        logger.info(
            f"logout: {request_data.user_name} remove room = {pre_room._user_name}"
        )
        room_manager.remove_room(pre_room)
        return LogoutResponse(
            message=f"logout: {request_data.user_name} success",
        )

    except Exception as e:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"logout: {request_data.user_name} failed, error: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
