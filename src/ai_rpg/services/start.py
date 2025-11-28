"""游戏启动服务模块

本模块提供游戏启动的 API 接口，负责游戏会话的初始化和创建。主要功能包括：
- 验证用户房间状态，确保用户已登录
- 创建玩家会话（PlayerSession）实例
- 初始化或加载游戏世界（World）数据
- 创建游戏实例（TCGGame）并初始化 ECS 系统
- 验证玩家实体创建成功

游戏启动流程：
1. 验证房间存在且游戏未启动
2. 创建玩家会话
3. 加载或创建世界数据（当前仅支持新建，加载功能尚未实现）
4. 创建游戏实例
5. 根据世界状态决定是新建游戏还是恢复游戏
6. 初始化游戏系统
7. 验证玩家实体创建成功

注意事项：
- 必须先调用 login 接口创建房间，否则返回 404 错误
- 游戏已启动时不能重复启动，返回 400 错误
- 从存档加载游戏的功能尚未实现，会返回 500 错误
- 所有异常由 FastAPI 框架统一处理，确保客户端收到正确的 HTTP 状态码
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.player_session import PlayerSession
from ..game.tcg_game import TCGGame
from ..game.game_data_service import get_user_world_data, get_game_boot_data
from ..models import StartRequest, StartResponse, World
from .game_server_dependencies import CurrentGameServer
from ..demo.stage_dungeon4 import (
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

    处理游戏启动请求，完成游戏会话的初始化流程。
    该接口会创建玩家会话、初始化游戏世界、构建 ECS 系统，并验证游戏启动成功。

    Args:
        payload: 游戏启动请求数据，包含：
            - user_name: 用户名，用于定位用户房间
            - game_name: 游戏名称，用于加载游戏配置
            - actor_name: 玩家角色名称
        game_server: 游戏服务器实例，管理所有用户房间和游戏会话

    Returns:
        StartResponse: 游戏启动响应，包含启动成功的消息

    Raises:
        HTTPException(404): 用户房间不存在，需要先调用 login 接口
        HTTPException(400): 游戏已经在运行中，不能重复启动
        HTTPException(500): 以下情况会返回 500 错误：
            - 游戏启动配置数据不存在
            - 尝试从存档加载游戏（功能尚未实现）
            - 玩家实体创建失败
        AssertionError: 当关键对象状态异常时抛出

    Note:
        - 必须先调用 /api/login/v1/ 创建用户房间
        - 当前仅支持创建新游戏，不支持从存档加载
        - 游戏会自动创建 demo 地下城（测试功能）
        - 游戏启动后会立即初始化并保存初始状态
        - 如果世界数据中已有实体，会尝试恢复游戏状态
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

    # 检查游戏是否已经在进行中
    if room._tcg_game is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start/v1: {payload.user_name} game is already running",
        )

    # 创建玩家客户端
    room._player_session = PlayerSession(
        name=payload.user_name,
        actor=payload.actor_name,
        game=payload.game_name,
    )
    assert room._player_session is not None, "房间玩家客户端实例不存在"

    # 获取或创建世界数据
    current_world_instance = get_user_world_data(payload.user_name, payload.game_name)
    if current_world_instance is None:

        # 如果没有world数据，就创建一个新的world
        world_boot = get_game_boot_data(payload.game_name)
        assert world_boot is not None, "world_boot is None"
        if world_boot is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"start/v1: {payload.game_name} boot data not found",
            )

        # 重新生成world
        current_world_instance = World(boot=world_boot)

        # 测试：如果是demo游戏，就创建demo地下城
        current_world_instance.dungeon = create_demo_dungeon4()

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
        room._tcg_game.new_game().save()
    else:
        logger.info(
            f"游戏中有实体 = {payload.game_name}，需要通过数据恢复实体，是游戏的恢复的过程"
        )
        room._tcg_game.load_game().save()

    # 验证玩家实体是否创建成功
    player_entity = room._tcg_game.get_player_entity()
    if player_entity is None:
        logger.error(f"没有找到玩家实体 = {payload.actor_name}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"start/v1: {payload.user_name} failed to create player entity",
        )

    # 必须初始化游戏！
    logger.info(f"start/v1: {payload.user_name} init game!")
    await room._tcg_game.initialize()

    # 返回成功响应
    return StartResponse(
        message=f"启动游戏成功！",
    )
