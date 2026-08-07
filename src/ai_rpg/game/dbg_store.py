"""
游戏存储模块 —— 统一 flush + archive 操作

封装 flush_entities() → archive_world() 的标准存储流程，
保证每次持久化前 ECS 运行时状态已同步到序列化模型。
"""

from pathlib import Path
from typing import Optional
from .dbg_game import DBGGame
from .world_store import archive_world
from .config import WORLDS_DIR


def store_game(dbg_game: DBGGame, save_dir: Optional[Path] = None) -> bool:
    """先刷新实体状态再持久化存档。"""
    dbg_game.flush_entities()
    return archive_world(
        dbg_game._world,
        dbg_game._player_session,
        worlds_dir=WORLDS_DIR,
        save_dir=save_dir,
    )
