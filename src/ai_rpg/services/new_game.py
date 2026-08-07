"""新游戏启动服务模块"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..models import PlayerSession
from ..game.dbg_game import DBGGame
from ..models import (
    NewGameRequest,
    NewGameResponse,
    World,
    Blueprint,
    Dungeon,
    BlueprintListResponse,
)
from .game_server_dependencies import CurrentGameServer
from ..game.config import BLUEPRINTS_DIR
from ..game.world_store import archive_world

###################################################################################################################################################################
new_game_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@new_game_api_router.get(
    path="/api/game/blueprint-list/v1/", response_model=BlueprintListResponse
)
async def list_blueprints() -> BlueprintListResponse:
    """获取可用蓝图列表接口"""
    blueprints = [
        Blueprint.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(BLUEPRINTS_DIR.glob("*.json"))
    ]
    return BlueprintListResponse(blueprints=blueprints)


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@new_game_api_router.post(path="/api/game/new/v1/", response_model=NewGameResponse)
async def new_game(
    payload: NewGameRequest,
    game_server: CurrentGameServer,
) -> NewGameResponse:
    """新游戏启动接口"""

    logger.info(f"/api/game/new/v1/: {payload.model_dump_json()}")

    # 检查房间是否存在
    if not game_server.has_room(payload.user_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"game/new/v1: {payload.user_name} not found, create room",
        )

    # 获取房间实例
    room = game_server.get_room(payload.user_name)
    assert room is not None, "new_game: room instance is None"

    # 从 BLUEPRINTS_DIR 加载蓝图 JSON 文件
    blueprint_path = BLUEPRINTS_DIR / f"{payload.game_name}.json"
    if not blueprint_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"game/new/v1: blueprint file not found for game '{payload.game_name}'",
        )
    blueprint_data = Blueprint.model_validate_json(
        blueprint_path.read_text(encoding="utf-8")
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
        entities=[],
        agents_context={},
        dungeon=Dungeon(name="", rooms=[], premise=""),
        blueprint=blueprint_data,
    )

    # 依赖注入，创建新的游戏
    assert world_data is not None, "World data must exist to create a game"
    room._dbg_game = DBGGame(
        name=payload.game_name,
        player_session=room._player_session,
        world=world_data,
    )

    # 根据蓝图构建游戏实例，并刷新实体数据到world中
    assert (
        len(room._dbg_game._world.entities) == 0
    ), "测试阶段，游戏中不应该有实体数据！"
    #

    # 执行游戏初始化逻辑，确保游戏状态正确设置，准备好接受玩家的操作
    await room._dbg_game.initialize()

    # 存档初始世界状态，便于调试和回放
    room._dbg_game.build_from_blueprint().flush_entities()
    archive_world(room._dbg_game._world, room._dbg_game._player_session)

    # 返回成功响应
    return NewGameResponse(
        blueprint=blueprint_data, player_session=room._player_session
    )
