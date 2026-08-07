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
from ai_rpg.game.config import (
    BLUEPRINTS_DIR,
    DUNGEONS_DIR,
)
from ai_rpg.models import PlayerSession
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import Blueprint, Dungeon, World
from ai_rpg.game.dbg_store import store_game
from pathlib import Path


###############################################################################
async def create_and_initialize_game(
    user: str, game: str, dungeon_name: str, save_dir: Path
) -> DBGGame:
    """从蓝图文件和副本文件创建并初始化新游戏实例，完成后归档。副本文件缺失时使用空副本占位。"""
    # 从 JSON 文件加载蓝图
    blueprint_path = BLUEPRINTS_DIR / f"{game}.json"
    assert blueprint_path.exists(), f"蓝图文件不存在: {blueprint_path}"
    world_blueprint = Blueprint.model_validate_json(
        blueprint_path.read_text(encoding="utf-8")
    )
    assert world_blueprint is not None, "world blueprint 反序列化失败"

    # 从 JSON 文件加载副本；名称为空或文件不存在时使用空副本占位
    dungeon_path = DUNGEONS_DIR / f"{dungeon_name}.json"
    if dungeon_name and dungeon_path.exists():
        dungeon = Dungeon.model_validate_json(dungeon_path.read_text(encoding="utf-8"))
    else:
        logger.warning(
            f"副本文件未找到（dungeon_name={dungeon_name!r}），使用空副本占位"
        )
        dungeon = Dungeon(name="", rooms=[], premise="")

    world_data = World(
        entity_counter=1000,
        entities=[],
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

    assert len(terminal_game._world.entities) == 0, "测试阶段，游戏中不应该有实体数据！"
    # terminal_game.build_from_blueprint().flush_entities()

    await terminal_game.initialize()

    logger.info(
        f"游戏创建并初始化完成：user={user}, game={game}, dungeon={dungeon_name}"
    )

    # 持久化游戏世界数据到存档目录，并启用 gzip 快照功能
    store_game(terminal_game, save_dir)

    # 返回游戏实例
    return terminal_game


###############################################################################
async def restore_game(
    world: World,
    player_session: PlayerSession,
) -> DBGGame:
    """从 World/PlayerSession 快照还原 DBGGame 实例。所有动作命令的共享入口。"""
    game = str(world.blueprint.name)
    terminal_game = DBGGame(
        name=game,
        player_session=player_session,
        world=world,
    )
    terminal_game.restore_from_snapshot()
    await terminal_game.initialize()
    logger.info(f"游戏已从存档恢复：user={player_session.name}, game={game}")
    return terminal_game
