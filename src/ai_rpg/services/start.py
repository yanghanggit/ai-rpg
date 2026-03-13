"""游戏启动服务模块

提供游戏启动 API 接口，负责创建玩家会话和初始化游戏实例。
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.player_session import PlayerSession
from ..game.tcg_game import TCGGame
from ..models import StartRequest, StartResponse, World
from .game_server_dependencies import CurrentGameServer
from ..demo import create_mountain_beasts_dungeon, create_hunter_mystic_blueprint
from ..game.config import GAME_1

###################################################################################################################################################################
start_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@start_api_router.post(path="/api/start/v1/", response_model=StartResponse)
async def start(
    payload: StartRequest,
    game_server: CurrentGameServer,
) -> StartResponse:
    """游戏启动接口

    创建并初始化游戏会话。

    Args:
        payload: 启动请求对象
        game_server: 游戏服务器实例

    Returns:
        StartResponse: 包含游戏蓝图配置的启动响应

    Raises:
        HTTPException(404): 用户房间不存在
        HTTPException(400): 游戏已在运行中
        HTTPException(500): 游戏蓝图不存在或玩家实体创建失败
    """

    logger.info(f"/api/start/v1/: {payload.model_dump_json()}")

    # 检查房间是否存在
    if not game_server.has_room(payload.user_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"start/v1: {payload.user_name} not found, create room",
        )

    # 获取房间实例
    room = game_server.get_room(payload.user_name)
    assert room is not None, "start: room instance is None"

    # 如果没有blueprint数据，就返回错误, 压根不能玩！
    assert payload.game_name == GAME_1, f"目前仅支持 {GAME_1} 这个游戏蓝图"
    blueprint_data = create_hunter_mystic_blueprint(payload.game_name)
    assert blueprint_data is not None, "world_blueprint is None"
    if blueprint_data is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"start/v1: {payload.game_name} blueprint data not found",
        )

    # 创建玩家客户端
    room._player_session = PlayerSession(
        name=payload.user_name,
        actor=blueprint_data.player_actor,
        game=payload.game_name,
    )
    assert room._player_session is not None, "房间玩家客户端实例不存在"

    # 重新生成world
    world_data = World(
        entity_counter=1000,
        entities_serialization=[],
        agents_context={},
        dungeon=create_mountain_beasts_dungeon(),
        blueprint=blueprint_data,
    )

    # 依赖注入，创建新的游戏
    assert world_data is not None, "World data must exist to create a game"
    room._tcg_game = TCGGame(
        name=payload.game_name,
        player_session=room._player_session,
        world=world_data,
    )

    # 根据蓝图构建游戏实例，并刷新实体数据到world中
    assert (
        len(room._tcg_game.world.entities_serialization) == 0
    ), "测试阶段，游戏中不应该有实体数据！"
    room._tcg_game.build_from_blueprint().flush_entities()

    # 执行游戏初始化逻辑，确保游戏状态正确设置，准备好接受玩家的操作
    await room._tcg_game.initialize()

    # 返回成功响应
    return StartResponse(blueprint=blueprint_data)
