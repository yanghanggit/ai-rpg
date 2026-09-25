"""用户登录登出服务模块"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ..models import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
)
from .game_server_dependencies import CurrentGameServer

###################################################################################################################################################################
login_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@login_api_router.post(path="/api/login/v1/", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    game_server: CurrentGameServer,
) -> LoginResponse:
    """用户登录接口"""

    logger.info(f"/api/login/v1/: {payload.model_dump_json()}")

    # TODO, 开发期的设置，强制删除运行中的房间，这样就不用考虑清库的问题。
    if game_server.has_room(payload.user_name):

        # 获取房间实例
        pre_room = game_server.get_room(payload.user_name)
        assert pre_room is not None, "login: room instance is None"

        # 删除房间实例：remove_room 会等待该房间进行中的事务结束再关闭
        await game_server.remove_room(payload.user_name)
        logger.info(
            f"login: {payload.user_name} has room, remove it = {pre_room.username}"
        )

    # 登录成功就开个空的房间!
    if not game_server.has_room(payload.user_name):

        # 创建新房间
        new_room = await game_server.create_room(
            user_name=payload.user_name,
        )
        logger.info(f"login: {payload.user_name} create room = {new_room.username}")
        assert new_room.game is None, "新创建的房间不应该有游戏实例"

    # 如果有房间，就获取房间。
    assert (
        game_server.get_room(payload.user_name) is not None
    ), "login: room instance is None"
    return LoginResponse(
        message=f"{payload.user_name} 登录成功！并创建房间！",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@login_api_router.post(path="/api/logout/v1/", response_model=LogoutResponse)
async def logout(
    payload: LogoutRequest,
    game_server: CurrentGameServer,
) -> LogoutResponse:
    """用户登出接口"""

    logger.info(f"/api/logout/v1/: {payload.model_dump_json()}")

    # 先检查房间是否存在
    if not game_server.has_room(payload.user_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"logout: {payload.user_name} not found",
        )

    # 获取房间实例
    pre_room = game_server.get_room(payload.user_name)
    assert pre_room is not None, "logout: room instance is None"

    # 在房间事务锁内退出游戏，避免与后台任务并发写坏状态
    async with pre_room.transaction():

        # 只判断dbg_game是否存在
        game = pre_room.game
        if game is not None:

            # 保存游戏的运行时数据
            # game.save_game()
            logger.info(f"logout: {payload.user_name} save game = {game.name}")

            # 退出游戏
            game.exit()
            logger.info(f"logout: {payload.user_name} exit game = {game.name}")

        else:
            logger.info(
                f"logout: {payload.user_name} no dbg game = {pre_room.username}"
            )

    # 游戏已经存储并退出,删除房间实例（会等待进行中的事务结束再关闭）
    await game_server.remove_room(payload.user_name)
    logger.info(f"logout: {payload.user_name} remove room = {pre_room.username}")

    # 返回成功响应
    return LogoutResponse(
        message=f"logout: {payload.user_name} success",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
