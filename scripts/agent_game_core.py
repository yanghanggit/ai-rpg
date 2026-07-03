"""游戏动作基础设施层。

提供游戏实例的创建与从存档复位的共享入口，供各动作模块 import 使用。
"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
# 将 scripts 目录添加到模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from ai_rpg.deepseek import DeepSeekClient
from ai_rpg.game.config import (
    BLUEPRINTS_DIR,
    DUNGEONS_DIR,
)
from ai_rpg.models import PlayerSession
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import Blueprint, Dungeon, World
from ai_rpg.game import archive_world
from pathlib import Path


###############################################################################
async def create_and_initialize_game(
    user: str, game: str, dungeon_name: str, save_dir: Path
) -> DBGGame:
    """创建并初始化一个新游戏实例。

    从 BLUEPRINTS_DIR/{game}.json 加载蓝图，从 DUNGEONS_DIR/{dungeon_name}.json 加载地下城。

    Args:
        user: 玩家用户名
        game: 游戏名称（对应 BLUEPRINTS_DIR 下的文件名）
        dungeon_name: 地下城名称（对应 DUNGEONS_DIR 下的文件名）
        save_dir: 存档目录

    Returns:
        已初始化完成的 DBGGame 实例
    """
    # 从 JSON 文件加载蓝图
    blueprint_path = BLUEPRINTS_DIR / f"{game}.json"
    assert blueprint_path.exists(), f"蓝图文件不存在: {blueprint_path}"
    world_blueprint = Blueprint.model_validate_json(
        blueprint_path.read_text(encoding="utf-8")
    )
    assert world_blueprint is not None, "world blueprint 反序列化失败"

    # 从 JSON 文件加载地下城；名称为空或文件不存在时使用空地下城占位
    dungeon_path = DUNGEONS_DIR / f"{dungeon_name}.json"
    if dungeon_name and dungeon_path.exists():
        dungeon = Dungeon.model_validate_json(dungeon_path.read_text(encoding="utf-8"))
    else:
        logger.warning(
            f"地下城文件未找到（dungeon_name={dungeon_name!r}），使用空地下城占位"
        )
        dungeon = Dungeon(name="", rooms=[], ecology="")

    world_data = World(
        entity_counter=1000,
        home_planning_turn_index=0,
        entities_serialization=[],
        agents_context={},
        dungeon=dungeon,
        blueprint=world_blueprint,
    )

    assert world_data is not None, "World data must exist to create a game"
    terminal_game = DBGGame(
        name=game,
        player_session=PlayerSession(
            name=user,
            actor=world_data.blueprint.player_actor,
            game=game,
        ),
        world=world_data,
    )

    DeepSeekClient.setup()
    # ImageClient.setup(server_configuration.replicate_image_generation_server_port)

    assert (
        len(terminal_game._world.entities_serialization) == 0
    ), "测试阶段，游戏中不应该有实体数据！"
    terminal_game.build_from_blueprint().flush_entities()

    await terminal_game.initialize()

    logger.info(
        f"游戏创建并初始化完成：user={user}, game={game}, dungeon={dungeon_name}"
    )

    # 并发检查图片服务
    # await ImageClient.health_check()

    # 持久化游戏世界数据到存档目录，并启用 gzip 快照功能
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def restore_game(
    world: World,
    player_session: PlayerSession,
) -> DBGGame:
    """从已还原的 World/PlayerSession 构造 DBGGame 并完成初始化。

    各命令的共享入口：先由命令层调用 restore_world(snapshot_path) 拿到
    (World, PlayerSession)，再传入本函数完成 DBGGame 的实体重建与服务初始化。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。

    Returns:
        已完成 restore_from_snapshot() + initialize() 的 DBGGame 实例，
        可直接调用 home_pipeline / combat_pipeline。
    """
    game = str(world.blueprint.name)
    terminal_game = DBGGame(
        name=game,
        player_session=player_session,
        world=world,
    )
    DeepSeekClient.setup()
    # ImageClient.setup(server_configuration.replicate_image_generation_server_port)
    terminal_game.restore_from_snapshot()
    await terminal_game.initialize()
    logger.info(f"游戏已从存档恢复：user={player_session.name}, game={game}")
    return terminal_game
