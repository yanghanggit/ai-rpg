"""世界持久化模块

提供游戏世界数据的持久化和调试功能，包括蓝图配置、世界运行时数据、玩家会话等的读写操作。

主要功能：
- 读取游戏蓝图配置（get_game_blueprint_data）
- 读取/保存/删除用户世界数据（get_user_world_data, persist_world_data, delete_user_world_data）
- 调试输出：保存详细的游戏状态到日志目录（debug_verbose_world_data 及相关函数）
"""

import gzip
import shutil
from pathlib import Path
from typing import Optional
from loguru import logger
from ..models import Blueprint, World, Dungeon
from .player_session import PlayerSession
from .config import WORLD_BLUEPRINT_DIR, WORLD_RUNTIME_DIR
from .config import LOGS_DIR


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
def get_game_blueprint_data(game: str) -> Optional[Blueprint]:
    """从本地文件系统加载游戏蓝图配置

    从 WORLD_BLUEPRINT_DIR 目录读取游戏的蓝图配置文件（{game}.json）。
    蓝图包含游戏的初始配置，如玩家角色、场景、物品等静态数据。

    Args:
        game: 游戏名称，用于定位配置文件

    Returns:
        Blueprint: 游戏蓝图对象，包含游戏的完整配置
        None: 文件不存在或解析失败时返回 None
    """

    read_path = WORLD_BLUEPRINT_DIR / f"{game}.json"
    assert read_path.exists(), f"游戏启动数据文件不存在: {read_path}"
    if not read_path.exists():
        return None

    try:

        logger.debug(f"📖 从本地文件系统获取演示游戏世界进行验证...")
        json_data = read_path.read_text(encoding="utf-8")
        blueprint_data = Blueprint.model_validate_json(json_data)
        return blueprint_data

    except Exception as e:
        logger.error(f"❌ 从本地文件系统获取演示游戏世界失败: {str(e)}")

    return None


###############################################################################################################################################
def get_user_world_data(user: str, game: str) -> Optional[World]:
    """加载用户的游戏世界运行时数据

    从 WORLD_RUNTIME_DIR/{user}/{game}/runtime.json 读取世界状态。
    运行时数据包含实体状态、代理上下文、地下城等动态游戏数据。

    Args:
        user: 用户名
        game: 游戏名称

    Returns:
        World: 世界运行时对象，包含完整的游戏状态
        None: 文件不存在或读取失败时返回 None
    """
    read_path = WORLD_RUNTIME_DIR / user / game / "runtime.json"
    if not read_path.exists():
        return None

    try:

        logger.debug(f"📖 从本地文件系统获取用户游戏世界数据...")
        world_json = read_path.read_text(encoding="utf-8")
        world_data = World.model_validate_json(world_json)
        return world_data

    except Exception as e:
        logger.error(f"❌ 从本地文件系统获取用户游戏世界数据失败: {str(e)}")

    return None


###############################################################################################################################################
def delete_user_world_data(user: str, game: str) -> bool:
    """删除用户的游戏世界数据目录

    删除 WORLD_RUNTIME_DIR/{user}/{game} 目录及其所有内容，
    包括 runtime.json、blueprint.json 等所有保存的游戏数据。

    Args:
        user: 用户名
        game: 游戏名称

    Returns:
        bool: 删除成功返回 True，目录不存在返回 False
    """
    write_dir = WORLD_RUNTIME_DIR / user / game
    if write_dir.exists():
        shutil.rmtree(write_dir)
        logger.debug(f"🗑️ 已删除用户游戏世界数据目录: {write_dir}")
        return True

    return False


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
def persist_world_data(
    username: str, world: World, player_session: PlayerSession, enable_gzip: bool = True
) -> bool:
    """持久化游戏世界数据到本地文件系统

    保存完整的游戏状态到 WORLD_RUNTIME_DIR/{username}/{game}/ 目录，包括：
    - runtime.json: 世界运行时数据（实体、代理、地下城等）
    - blueprint.json: 游戏蓝图配置
    - player_session.json: 玩家会话数据
    - runtime.json.gz: 压缩版本的运行时数据（可选）

    Args:
        username: 用户名
        world: 世界对象，包含完整的游戏状态
        player_session: 玩家会话对象
        enable_gzip: 是否同时保存 gzip 压缩版本，默认为 True

    Returns:
        bool: 保存成功返回 True，失败返回 False
    """
    game = str(world.blueprint.name)
    write_dir = WORLD_RUNTIME_DIR / username / game
    write_dir.mkdir(parents=True, exist_ok=True)
    assert write_dir.exists(), f"找不到目录: {write_dir}"

    try:
        # 序列化世界数据（只调用一次）
        world_json = world.model_dump_json()

        # 保存 runtime.json
        write_path = write_dir / "runtime.json"
        write_path.write_text(world_json, encoding="utf-8")
        # logger.debug(f"💾 已保存用户游戏世界数据到文件: {write_path}")

        # 保存 blueprint.json
        write_blueprint_path = write_dir / "blueprint.json"
        write_blueprint_path.write_text(
            world.blueprint.model_dump_json(), encoding="utf-8"
        )
        # logger.debug(f"💾 已保存用户游戏启动数据到文件: {write_blueprint_path}")

        # 保存 player_session.json
        write_player_session_path = write_dir / "player_session.json"
        write_player_session_path.write_text(
            player_session.model_dump_json(), encoding="utf-8"
        )
        # logger.debug(f"💾 已保存用户玩家会话数据到文件: {write_player_session_path}")

        # 如果需要，保存压缩版本
        if enable_gzip:
            gzip_path = write_dir / "runtime.json.gz"
            with gzip.open(gzip_path, "wt", encoding="utf-8") as gz_file:
                gz_file.write(world_json)
            # logger.debug(f"💾 已保存用户游戏世界数据到压缩文件: {gzip_path}")

        return True

    except Exception as e:
        logger.error(f"❌ 保存用户游戏世界数据失败: {str(e)}")

    return False


###############################################################################################################################################
def ensure_debug_dir(player_session_name: str, game_name: str) -> Path:
    """获取或创建调试日志目录

    返回用于保存详细游戏状态的目录路径，如果目录不存在则自动创建。

    Args:
        player_session_name: 玩家会话名称
        game_name: 游戏名称

    Returns:
        Path: 日志目录路径 LOGS_DIR/{player_session_name}/{game_name}
    """
    dir = LOGS_DIR / f"{player_session_name}" / f"{game_name}"
    if not dir.exists():
        dir.mkdir(parents=True, exist_ok=True)
    assert dir.exists()
    assert dir.is_dir()
    return dir


###############################################################################################################################################
def dump_world_snapshot(
    verbose_dir: Path, world: World, player_session: PlayerSession
) -> None:
    """保存完整的游戏状态到调试日志目录

    综合调用所有 verbose 函数，保存游戏的所有详细信息，包括蓝图、世界数据、
    实体序列化、代理上下文、玩家会话和地下城数据。

    Args:
        verbose_dir: 日志输出目录
        world: 世界对象
        player_session: 玩家会话对象
    """
    dump_blueprint(verbose_dir, world)
    dump_world_state(verbose_dir, world)
    dump_entities(verbose_dir, world)
    dump_agent_contexts(verbose_dir, world)
    dump_player_session(verbose_dir, player_session)
    dump_dungeon(verbose_dir, world.dungeon)


###############################################################################################################################################
def dump_agent_contexts(
    verbose_dir: Path, world: World, should_write_buffer_string: bool = True
) -> None:
    """保存代理对话上下文到调试目录

    为每个代理保存其对话历史，包括 JSON 格式和可读的文本格式。

    Args:
        verbose_dir: 日志输出目录
        world: 世界对象，包含所有代理的上下文
        should_write_buffer_string: 是否同时保存可读的文本格式，默认为 True
    """
    context_dir = verbose_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    for agent_name, agent_context in world.agents_context.items():
        context_path = context_dir / f"{agent_name}.json"
        context_path.write_text(agent_context.model_dump_json(), encoding="utf-8")

        if should_write_buffer_string:
            from langchain_core.messages import get_buffer_string

            buffer_str = get_buffer_string(
                agent_context.context,
                human_prefix=f"""\nHuman""",
                ai_prefix=f"""\nAI({agent_name})""",
            )
            context_path2 = context_dir / f"{agent_name}_buffer.txt"
            context_path2.write_text(buffer_str, encoding="utf-8")


###############################################################################################################################################
def dump_blueprint(verbose_dir: Path, world: World) -> None:
    """保存游戏蓝图配置到调试目录

    保存蓝图到 blueprint_data 子目录。如果文件已存在则跳过，避免覆盖。

    Args:
        verbose_dir: 日志输出目录
        world: 世界对象，包含蓝图配置
    """
    blueprint_data_dir = verbose_dir / "blueprint_data"
    blueprint_data_dir.mkdir(parents=True, exist_ok=True)

    blueprint_file_path = blueprint_data_dir / f"{world.blueprint.name}.json"
    if blueprint_file_path.exists():
        return  # 如果文件已存在，则不覆盖

    # 保存 blueprint 数据到文件
    blueprint_file_path.write_text(world.blueprint.model_dump_json(), encoding="utf-8")


###############################################################################################################################################
def dump_world_state(verbose_dir: Path, world: World) -> None:
    """保存完整世界数据到调试目录

    保存世界的完整状态到 world_data 子目录，每次调用会覆盖已有文件。

    Args:
        verbose_dir: 日志输出目录
        world: 世界对象
    """
    world_data_dir = verbose_dir / "world_data"
    world_data_dir.mkdir(parents=True, exist_ok=True)
    world_file_path = world_data_dir / f"{world.blueprint.name}.json"
    world_file_path.write_text(
        world.model_dump_json(), encoding="utf-8"
    )  # 保存 World 数据到文件，覆盖


###############################################################################################################################################
def dump_player_session(verbose_dir: Path, player_session: PlayerSession) -> None:
    """保存玩家会话数据到调试目录

    保存玩家会话信息到 player_session 子目录。

    Args:
        verbose_dir: 日志输出目录
        player_session: 玩家会话对象
    """
    player_session_dir = verbose_dir / "player_session"
    player_session_dir.mkdir(parents=True, exist_ok=True)

    player_session_file_path = player_session_dir / f"{player_session.name}.json"
    player_session_file_path.write_text(
        player_session.model_dump_json(), encoding="utf-8"
    )


###############################################################################################################################################
def dump_entities(verbose_dir: Path, world: World) -> None:
    """保存所有实体序列化数据到调试目录

    为每个实体保存独立的 JSON 文件到 entities_serialization 子目录。
    每次调用会先删除旧目录再创建新目录，确保数据是最新的。

    Args:
        verbose_dir: 日志输出目录
        world: 世界对象，包含所有实体的序列化数据
    """
    entities_serialization_dir = verbose_dir / "entities_serialization"
    # 强制删除一次
    if entities_serialization_dir.exists():
        shutil.rmtree(entities_serialization_dir)
    # 创建目录
    entities_serialization_dir.mkdir(parents=True, exist_ok=True)
    assert entities_serialization_dir.exists()

    for entity_serialization in world.entities_serialization:
        entity_serialization_path = (
            entities_serialization_dir / f"{entity_serialization.name}.json"
        )
        entity_serialization_path.write_text(
            entity_serialization.model_dump_json(), encoding="utf-8"
        )


###############################################################################################################################################
def dump_dungeon(verbose_dir: Path, dungeon: Dungeon) -> None:
    """保存地下城数据到调试目录

    保存地下城配置和状态到 dungeons 子目录。

    Args:
        verbose_dir: 日志输出目录
        dungeon: 地下城对象
    """
    dungeon_system_dir = verbose_dir / "dungeons"
    dungeon_system_dir.mkdir(parents=True, exist_ok=True)
    dungeon_system_path = dungeon_system_dir / f"{dungeon.name}.json"
    dungeon_system_path.write_text(dungeon.model_dump_json(), encoding="utf-8")


###############################################################################################################################################
