"""游戏启动服务模块

提供游戏启动 API 接口，负责创建玩家会话和初始化游戏实例。
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.player_session import PlayerSession
from ..game.tcg_game import TCGGame
from ..game.world_persistence import get_user_world_data, get_game_blueprint_data
from ..models import StartRequest, StartResponse, World
from .game_server_dependencies import CurrentGameServer
from ..demo.dungeon_mountain_beasts import (
    create_mountain_beasts_dungeon,
)

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
    world_blueprint = get_game_blueprint_data(payload.game_name)
    assert world_blueprint is not None, "world_blueprint is None"
    if world_blueprint is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"start/v1: {payload.game_name} blueprint data not found",
        )

    # 检查游戏是否已经在进行中
    if room._tcg_game is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start/v1: {payload.user_name} game is already running",
        )

    # 创建玩家客户端
    room._player_session = PlayerSession(
        name=payload.user_name,
        actor=world_blueprint.player_actor,
        game=payload.game_name,
    )
    assert room._player_session is not None, "房间玩家客户端实例不存在"

    # 获取或创建世界数据
    current_world_instance = get_user_world_data(payload.user_name, payload.game_name)
    if current_world_instance is None:

        # 重新生成world
        current_world_instance = World(
            runtime_index=1000,
            entities_serialization=[],
            agents_context={},
            dungeon=create_mountain_beasts_dungeon(),
            blueprint=world_blueprint,
        )

    else:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"start/v1: {payload.user_name} load world data not implemented",
        )

    # 依赖注入，创建新的游戏
    assert current_world_instance is not None, "World data must exist to create a game"
    room._tcg_game = TCGGame(
        name=payload.game_name,
        player_session=room._player_session,
        world=current_world_instance,
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(room._tcg_game.world.entities_serialization) == 0:
        logger.info(
            f"游戏中没有实体 = {payload.game_name}, 说明是第一次创建游戏, 直接构建ECS!"
        )
        room._tcg_game.new_game().save_game()
    else:
        assert False, "start/v1: 游戏恢复功能尚未实现"

    # 验证玩家实体是否创建成功
    player_entity = room._tcg_game.get_player_entity()
    if player_entity is None:

        # 清理游戏实例, 出了严重的问题！！！
        room._tcg_game = None

        # 返回错误！
        logger.error(f"没有找到玩家实体 = {world_blueprint.player_actor}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"start/v1: {payload.user_name} failed to create player entity",
        )

    # 必须初始化游戏！
    logger.info(f"start/v1: {payload.user_name} init game!")
    await room._tcg_game.initialize()

    # 返回成功响应
    return StartResponse(blueprint=world_blueprint)
