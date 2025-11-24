"""副本状态查询服务模块

本模块提供副本（Dungeon）状态查询的 API 接口，主要功能包括：
- 查询当前副本的状态信息
- 获取副本中场景与角色的分布情况
- 返回副本的详细数据（包括副本对象和场景映射）
- 专门为 TCG 游戏类型设计

副本状态查询流程：
1. 验证用户房间是否存在
2. 验证 TCG 游戏实例是否存在
3. 从游戏实例中获取场景与角色的分布映射
4. 获取当前副本对象数据
5. 返回副本状态信息

应用场景：
- 显示副本地图和房间分布
- 查看副本中的角色位置
- 副本探索进度展示
- 副本导航和路径规划

注意事项：
- 必须先创建房间并启动 TCG 游戏才能查询副本状态
- 本接口专门为 TCG 游戏设计，不支持 SDG 游戏
- 返回的数据包含场景映射和完整的副本对象
- 所有异常由 FastAPI 框架统一处理，确保客户端收到正确的 HTTP 状态码
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_depends import GameServerInstance
from ..models import (
    DungeonStateResponse,
)

###################################################################################################################################################################
dungeon_state_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_state_api_router.get(
    path="/api/dungeons/v1/{user_name}/{game_name}/state",
    response_model=DungeonStateResponse,
)
async def get_dungeon_state(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
) -> DungeonStateResponse:
    """查询副本状态接口

    查询 TCG 游戏中当前副本的状态信息，包括副本中场景与角色的分布映射以及副本对象的完整数据。
    本接口专门为 TCG 游戏设计，用于副本探索和状态查询。

    Args:
        game_server: 游戏服务器实例，管理所有用户房间和游戏会话
        user_name: 用户名，用于定位用户房间
        game_name: 游戏名称，用于请求日志记录

    Returns:
        DungeonStateResponse: 副本状态响应，包含：
            - mapping: 场景名称到角色列表的映射字典
            - dungeon: 当前副本对象的完整数据（包括房间、怪物、宝箱等）

    Raises:
        HTTPException(404): 以下情况会返回 404 错误：
            - 用户房间不存在，需要先调用 login 接口
            - TCG 游戏实例不存在，需要先调用 start 接口
        AssertionError: 当关键对象状态异常时抛出

    Note:
        - 必须先调用 /api/login/v1/ 创建房间
        - 必须先调用 /api/start/v1/ 启动 TCG 游戏
        - 本接口专门为 TCG 游戏设计，不支持 SDG 游戏
        - 返回的 mapping 数据结构为 {场景名称: [角色名称列表], ...}
        - dungeon 字段包含副本的完整数据，包括房间布局、怪物分布等
        - 可用于显示副本地图、角色位置和副本探索进度
        - 数据实时反映游戏中副本的当前状态
    """

    logger.info(f"/dungeons/v1/{user_name}/{game_name}/state: {user_name}, {game_name}")

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        logger.error(f"view_dungeon: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例并检查 TCG 游戏是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "get_dungeon_state: room instance is None"
    if current_room._tcg_game is None:
        logger.error(f"view_dungeon: {user_name} has no game")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏",
        )

    # 获取 TCG 游戏实例
    web_game = current_room._tcg_game

    # 获取场景与角色的分布映射
    mapping_data = web_game.get_stage_actor_distribution_mapping()
    logger.info(f"view_dungeon: {user_name} mapping_data: {mapping_data}")

    # 返回副本状态
    return DungeonStateResponse(
        mapping=mapping_data,
        dungeon=web_game.current_dungeon,
    )
