"""用户登录登出服务模块

提供用户登录和登出的 API 接口。
登录时创建用户房间，登出时保存游戏数据并清理房间。
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.world_persistence import delete_user_world_data
from ..game.config import WORLDS_DIR
from .game_server_dependencies import CurrentGameServer
from ..models import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
)

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
    """用户登录接口

    处理用户登录请求，创建用户专属的游戏房间实例。

    Args:
        payload: 登录请求数据
        game_server: 游戏服务器实例

    Returns:
        LoginResponse: 登录响应，包含登录成功的消息
    """

    logger.info(f"/api/login/v1/: {payload.model_dump_json()}")

    # TODO, 开发期的设置，强制删除运行中的房间，这样就不用考虑清库的问题。
    if game_server.has_room(payload.user_name):

        # 获取房间实例
        pre_room = game_server.get_room(payload.user_name)
        assert pre_room is not None, "login: room instance is None"

        # 直接删除房间实例
        game_server.remove_room(pre_room)
        logger.info(
            f"login: {payload.user_name} has room, remove it = {pre_room._username}"
        )

        # 直接删除运行中的游戏数据存档！
        delete_user_world_data(WORLDS_DIR, payload.user_name, payload.game_name)
        logger.info(
            f"这是测试，强制删除旧的游戏数据 = {payload.user_name}, {payload.game_name}"
        )

    # 登录成功就开个空的房间!
    if not game_server.has_room(payload.user_name):

        # 创建新房间
        new_room = game_server.create_room(
            user_name=payload.user_name,
        )
        logger.info(f"login: {payload.user_name} create room = {new_room._username}")
        assert new_room._tcg_game is None, "新创建的房间不应该有游戏实例"

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
    """用户登出接口

    处理用户登出请求，保存游戏数据并清理用户房间实例。

    Args:
        payload: 登出请求数据
        game_server: 游戏服务器实例

    Returns:
        LogoutResponse: 登出响应，包含登出成功的消息

    Raises:
        HTTPException(404): 用户房间不存在
    """

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

    # 只判断tcg_game是否存在
    if pre_room._tcg_game is not None:

        # 保存游戏的运行时数据
        pre_room._tcg_game.save_game()
        logger.info(
            f"logout: {payload.user_name} save game = {pre_room._tcg_game.name}"
        )

        # 退出游戏
        pre_room._tcg_game.exit()
        logger.info(
            f"logout: {payload.user_name} exit game = {pre_room._tcg_game.name}"
        )

    else:
        logger.info(f"logout: {payload.user_name} no tcg game = {pre_room._username}")

    # 游戏已经存储并退出,删除房间实例
    game_server.remove_room(pre_room)
    logger.info(f"logout: {payload.user_name} remove room = {pre_room._username}")

    # 返回成功响应
    return LogoutResponse(
        message=f"logout: {payload.user_name} success",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
