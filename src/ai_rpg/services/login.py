"""用户登录登出服务模块

本模块提供用户登录和登出的 API 接口，主要功能包括：
- 用户登录：创建用户房间实例，为用户分配游戏会话空间
- 用户登出：保存游戏数据，清理用户房间实例，释放资源

注意事项：
- 登录时会强制清理已存在的旧房间（开发期行为，后续可能调整）
- 登出时会检查房间是否存在，不存在则返回 404 错误
- 所有异常均由 FastAPI 框架统一处理，确保客户端能收到正确的 HTTP 状态码
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.game_data_service import delete_user_world_data
from .game_server_depends import GameServerInstance
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
###################################################################################################################################################################
@login_api_router.post(path="/api/login/v1/", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    game_server: GameServerInstance,
) -> LoginResponse:
    """用户登录接口

    处理用户登录请求，创建用户专属的游戏房间实例。
    开发期会强制删除已存在的旧房间和游戏数据，确保每次登录都是全新状态。

    Args:
        payload: 登录请求数据，包含用户名和游戏名
        game_server: 游戏服务器实例，管理所有用户房间

    Returns:
        LoginResponse: 登录响应，包含登录成功的消息

    Raises:
        AssertionError: 当房间创建失败或状态异常时抛出

    Note:
        - 开发期行为：会强制删除旧房间和游戏数据
        - 登录成功后会创建空房间，此时尚未加载游戏实例
        - 后续进入正式开发时，旧房间处理逻辑可能会调整或移除
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
        delete_user_world_data(payload.user_name, payload.game_name)
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
    game_server: GameServerInstance,
) -> LogoutResponse:
    """用户登出接口

    处理用户登出请求，保存游戏数据并清理用户房间实例。
    如果用户有正在进行的游戏，会先保存游戏数据再退出。

    Args:
        payload: 登出请求数据，包含用户名
        game_server: 游戏服务器实例，管理所有用户房间

    Returns:
        LogoutResponse: 登出响应，包含登出成功的消息

    Raises:
        HTTPException: 当用户房间不存在时，返回 404 NOT_FOUND
        AssertionError: 当房间实例状态异常时抛出

    Note:
        - 会检查房间是否存在，不存在则返回 404 错误
        - 如果有游戏实例，会先保存数据再退出游戏
        - 最后会删除房间实例，释放服务器资源
        - 所有异常由 FastAPI 自动处理，确保客户端收到正确的 HTTP 状态码
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
        pre_room._tcg_game.save()
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
