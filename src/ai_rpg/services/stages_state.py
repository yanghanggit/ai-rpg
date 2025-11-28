"""场景状态查询服务模块

本模块提供场景（Stages）状态查询的 API 接口，主要功能包括：
- 查询游戏中所有场景的状态信息
- 获取角色在各个场景中的分布情况
- 支持多种游戏类型（SDG 和 TCG 游戏）的场景查询
- 提供场景与角色的映射关系数据

场景状态查询流程：
1. 验证用户房间是否存在
2. 根据游戏类型（SDG 或 TCG）获取对应的游戏实例
3. 从游戏实例中提取场景与角色的分布映射数据
4. 返回场景状态信息

应用场景：
- 显示游戏地图和角色位置
- 查看各个场景中的角色分布
- 游戏状态可视化
- 场景管理和导航

注意事项：
- 必须先创建房间并启动游戏才能查询场景状态
- 支持 SDG 游戏和 TCG 游戏两种类型
- 游戏名称必须与当前运行的游戏匹配
- 返回的映射数据包含所有场景及其对应的角色列表
- 所有异常由 FastAPI 框架统一处理，确保客户端收到正确的 HTTP 状态码
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_dependencies import CurrentGameServer
from ..models import (
    StagesStateResponse,
)
from ..game.rpg_game import RPGGame

###################################################################################################################################################################
stages_state_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@stages_state_api_router.get(
    path="/api/stages/v1/{user_name}/{game_name}/state",
    response_model=StagesStateResponse,
)
async def get_stages_state(
    game_server: CurrentGameServer,
    user_name: str,
    game_name: str,
) -> StagesStateResponse:
    """查询场景状态接口

    查询游戏中所有场景的状态信息，包括场景与角色的分布映射关系。
    支持 SDG 和 TCG 两种游戏类型，返回场景及其包含的角色分布数据。

    Args:
        game_server: 游戏服务器实例，管理所有用户房间和游戏会话
        user_name: 用户名，用于定位用户房间
        game_name: 游戏名称，用于匹配当前运行的游戏

    Returns:
        StagesStateResponse: 场景状态响应，包含场景与角色的映射关系数据
            - mapping: 场景名称到角色列表的映射字典

    Raises:
        HTTPException(404): 用户房间不存在，需要先调用 login 接口
        HTTPException(400): 游戏名称与当前运行的游戏不匹配
        AssertionError: 当关键对象状态异常时抛出

    Note:
        - 必须先调用 /api/login/v1/ 创建房间
        - 必须先调用 /api/start/v1/ 或狼人杀启动接口启动游戏
        - 支持 SDG 游戏（_sdg_game）和 TCG 游戏（_tcg_game）
        - 游戏名称必须与房间中当前运行的游戏名称完全匹配
        - 返回的映射数据结构为 {场景名称: [角色名称列表], ...}
        - 可用于显示游戏地图、角色位置和场景导航
        - 映射数据实时反映游戏中角色在各场景的分布情况
    """

    logger.info(f"get_stages_state: {user_name}, {game_name}")

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        logger.error(f"view_home: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "get_stages_state: room instance is None"

    # 根据游戏类型获取游戏实例
    web_game: RPGGame | None = None

    if current_room._sdg_game is not None and game_name == current_room._sdg_game.name:
        # 获取 SDG 游戏
        web_game = current_room._sdg_game

    elif (
        current_room._tcg_game is not None and game_name == current_room._tcg_game.name
    ):
        # 获取 TCG 游戏
        web_game = current_room._tcg_game

    else:
        logger.error(f"get_session_messages: {user_name} game_name mismatch")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="游戏名称不匹配",
        )

    # 验证游戏实例
    assert web_game is not None, "WebGame should not be None"

    # 获取场景与角色的分布映射
    mapping_data = web_game.get_stage_actor_distribution_mapping()
    logger.info(f"view_home: {user_name} mapping_data: {mapping_data}")

    # 返回场景状态
    return StagesStateResponse(
        mapping=mapping_data,
    )
