"""世界存储模块

提供游戏世界数据的持久化与调试输出功能。

目录结构（persist_world_data）：
    {worlds_dir}/{username}/{game}/{timestamp}/
        ├── world.json              # 完整 World 序列化
        ├── player_session.json     # 完整 PlayerSession 序列化
        ├── entities/               # 各 ECS 实体单独一个 json
        ├── contexts/               # Agent LLM 对话上下文
        ├── dungeon/                # 地下城数据
        └── snapshot/               # (仅 enable_gzip=True)
            └── snapshot.zip        # 仅含 world.json + player_session.json

主要功能：
    - 持久化游戏世界（persist_world_data）
    - 完整快照输出（dump_world_snapshot）
    - Agent 对话上下文输出（dump_agent_contexts）
    - ECS 实体序列化输出（dump_entities）
    - 地下城数据输出（dump_dungeon）
    - 创建调试目录（ensure_debug_dir）
"""

import datetime
import shutil
import zipfile
from pathlib import Path

from langchain_core.messages import get_buffer_string
from loguru import logger

from .config import WORLDS_DIR
from .player_session import PlayerSession
from ..models import Dungeon, World


###############################################################################################################################################
def archive_world(
    world: World,
    player_session: PlayerSession,
    worlds_dir: Path = WORLDS_DIR,
    enable_gzip: bool = False,
) -> bool:
    """持久化游戏世界数据到带时间戳的存档目录。

    存档目录结构：
        {worlds_dir}/{username}/{game}/{timestamp}/
            ├── world.json
            ├── player_session.json
            ├── entities/{entity}.json ...
            ├── contexts/{agent}.json, {agent}_buffer.txt ...
            ├── dungeon/{dungeon_name}.json
            └── snapshot/snapshot.zip   (仅 enable_gzip=True)

    Args:
        world: 世界对象（含蓝图）
        player_session: 玩家会话对象
        worlds_dir: 存档根目录，默认 WORLDS_DIR
        enable_gzip: 为 True 时额外生成 snapshot/snapshot.zip，
                     内含 world.json + player_session.json

    Returns:
        保存成功返回 True，失败返回 False
    """
    username = player_session.name
    game = str(world.blueprint.name)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    save_dir = worlds_dir / username / game / timestamp
    save_dir.mkdir(parents=True, exist_ok=True)

    try:
        world_json = world.model_dump_json()
        player_session_json = player_session.model_dump_json()

        # world.json
        (save_dir / "world.json").write_text(world_json, encoding="utf-8")

        # player_session.json
        (save_dir / "player_session.json").write_text(
            player_session_json, encoding="utf-8"
        )

        # entities/
        _write_entities(save_dir, world)

        # contexts/
        _write_agent_contexts(save_dir, world)

        # dungeon/
        _write_dungeon(save_dir, world.dungeon)

        # snapshot/snapshot.zip (optional)
        if enable_gzip:
            snapshot_dir = save_dir / "snapshot"
            snapshot_dir.mkdir(exist_ok=True)
            zip_path = snapshot_dir / "snapshot.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("world.json", world_json)
                zf.writestr("player_session.json", player_session_json)

        logger.debug(f"存档成功: {save_dir}")
        return True

    except Exception as e:
        logger.error(f"存档失败: {e}")
        return False


###############################################################################################################################################
def _write_entities(save_dir: Path, world: World) -> None:
    entities_dir = save_dir / "entities"
    if entities_dir.exists():
        shutil.rmtree(entities_dir)
    entities_dir.mkdir(parents=True, exist_ok=True)

    for entity_serialization in world.entities_serialization:
        path = entities_dir / f"{entity_serialization.name}.json"
        path.write_text(entity_serialization.model_dump_json(), encoding="utf-8")


###############################################################################################################################################
def _write_agent_contexts(
    save_dir: Path, world: World, write_buffer_string: bool = True
) -> None:
    context_dir = save_dir / "contexts"
    context_dir.mkdir(parents=True, exist_ok=True)

    for agent_name, agent_context in world.agents_context.items():
        (context_dir / f"{agent_name}.json").write_text(
            agent_context.model_dump_json(), encoding="utf-8"
        )

        if write_buffer_string:
            buffer_str = get_buffer_string(
                agent_context.context,
                human_prefix="\n" + "-" * 86 + "\nHuman",
                ai_prefix=f"\n" + "-" * 86 + f"\nAI({agent_name})",
            )
            (context_dir / f"{agent_name}_buffer.txt").write_text(
                buffer_str, encoding="utf-8"
            )


###############################################################################################################################################
def _write_dungeon(save_dir: Path, dungeon: Dungeon) -> None:
    dungeon_dir = save_dir / "dungeon"
    dungeon_dir.mkdir(parents=True, exist_ok=True)
    (dungeon_dir / f"{dungeon.name}.json").write_text(
        dungeon.model_dump_json(), encoding="utf-8"
    )


###############################################################################################################################################
def dump_world_snapshot(debug_dir: Path, world: World) -> None:
    """输出完整的游戏状态快照到调试目录。

    Args:
        debug_dir: 调试目录路径
        world: 世界对象
    """
    dump_entities(debug_dir, world)
    dump_agent_contexts(debug_dir, world)
    dump_dungeon(debug_dir, world.dungeon)


###############################################################################################################################################
def dump_agent_contexts(
    debug_dir: Path, world: World, should_write_buffer_string: bool = True
) -> None:
    """输出 Agent 对话上下文到调试目录。

    Args:
        debug_dir: 调试目录路径
        world: 世界对象
        should_write_buffer_string: 是否同时输出可读文本格式
    """
    _write_agent_contexts(
        debug_dir, world, write_buffer_string=should_write_buffer_string
    )


###############################################################################################################################################
def dump_entities(debug_dir: Path, world: World) -> None:
    """输出所有 ECS 实体序列化数据到调试目录。

    Args:
        debug_dir: 调试目录路径
        world: 世界对象
    """
    _write_entities(debug_dir, world)


###############################################################################################################################################
def dump_dungeon(debug_dir: Path, dungeon: Dungeon) -> None:
    """输出地下城数据到调试目录。

    Args:
        debug_dir: 调试目录路径
        dungeon: 地下城对象
    """
    _write_dungeon(debug_dir, dungeon)


###############################################################################################################################################
def ensure_debug_dir(base_dir: Path, player_session_name: str, game_name: str) -> Path:
    """创建并返回调试日志目录。

    Args:
        base_dir: 基础目录
        player_session_name: 玩家会话名称
        game_name: 游戏名称

    Returns:
        调试目录路径
    """
    dir = base_dir / player_session_name / game_name
    dir.mkdir(parents=True, exist_ok=True)
    assert dir.exists() and dir.is_dir()
    return dir


###############################################################################################################################################
