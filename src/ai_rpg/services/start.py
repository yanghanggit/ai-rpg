"""游戏启动服务模块

提供游戏启动 API 接口，负责会话初始化和游戏创建。

主要流程：
1. 验证用户房间和游戏蓝图配置
2. 创建玩家会话和游戏实例
3. 初始化世界数据和 ECS 系统
4. 验证玩家实体并初始化游戏

注意：必须先调用 login 接口创建房间；当前仅支持新建游戏，暂不支持从存档加载。
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.player_session import PlayerSession
from ..game.tcg_game import TCGGame
from ..game.world_persistence import get_user_world_data, get_game_blueprint_data
from ..models import StartRequest, StartResponse, World
from .game_server_dependencies import CurrentGameServer
from ..demo.dungeon4 import (
    create_demo_dungeon4,
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

    创建并初始化游戏会话，包括玩家会话、世界数据、ECS 系统和玩家实体。

    Args:
        payload: 启动请求，包含 user_name（用户名）、game_name（游戏名）、actor_name（角色名）
        game_server: 游戏服务器实例，管理用户房间和会话

    Returns:
        StartResponse: 包含游戏蓝图配置的启动响应

    Raises:
        HTTPException(404): 用户房间不存在，需先调用 login 接口
        HTTPException(400): 游戏已在运行中，不能重复启动
        HTTPException(500): 游戏蓝图不存在、存档加载失败（未实现）或玩家实体创建失败

    Note:
        当前仅支持新建游戏。如有存档数据会返回错误，存档加载功能尚未实现。
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
            dungeon=create_demo_dungeon4(),
            blueprint=world_blueprint,
        )

        # 测试：如果是demo游戏，就创建demo地下城
        # current_world_instance.dungeon = create_demo_dungeon4()

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
