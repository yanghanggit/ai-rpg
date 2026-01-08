import gzip
import shutil
from pathlib import Path
from typing import Optional
from loguru import logger
from ..models import Blueprint, World, Dungeon
from .player_session import PlayerSession
from ..game.config import WORLD_BLUEPRINT_DIR, WORLD_RUNTIME_DIR
from .config import LOGS_DIR


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
def get_game_blueprint_data(game: str) -> Optional[Blueprint]:
    """
    全局方法：从本地文件系统获取指定游戏的启动世界数据

    Args:
        game: 游戏名称

    Returns:
        Blueprint 对象或 None
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
    """
    从本地文件系统获取用户的游戏世界运行时数据

    Args:
        user: 用户名
        game: 游戏名称

    Returns:
        World 对象或 None（如果文件不存在或读取失败）
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
    """
    删除用户的游戏世界数据目录

    Args:
        user: 用户名
        game: 游戏名称
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
    """
    持久化用户的游戏世界数据到本地文件系统

    保存内容包括：
    - runtime.json: 完整的世界运行时数据
    - blueprint.json: 游戏启动配置数据
    - runtime.json.gz: 压缩版本的世界数据（可选）

    Args:
        username: 用户名
        world: 要保存的世界对象
        player_session: 玩家会话对象
        use_gzip: 是否同时保存 gzip 压缩版本，默认为 True
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
def verbose_dir(player_session_name: str, game_name: str) -> Path:
    # 依赖 GameSession 提供的 name 属性
    dir = LOGS_DIR / f"{player_session_name}" / f"{game_name}"
    if not dir.exists():
        dir.mkdir(parents=True, exist_ok=True)
    assert dir.exists()
    assert dir.is_dir()
    return dir


###############################################################################################################################################
def debug_verbose_world_data(
    verbose_dir: Path, world: World, player_session: PlayerSession
) -> None:
    """调试方法，保存游戏状态到文件"""
    verbose_blueprint_data(verbose_dir, world)
    verbose_world_data(verbose_dir, world)
    verbose_entities_serialization(verbose_dir, world)
    verbose_context(verbose_dir, world)
    verbose_player_session(verbose_dir, player_session)
    verbose_dungeon(verbose_dir, world.dungeon)


###############################################################################################################################################
def verbose_context(
    verbose_dir: Path, world: World, should_write_buffer_string: bool = True
) -> None:
    """保存聊天历史到文件"""
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
def verbose_blueprint_data(verbose_dir: Path, world: World) -> None:
    """保存启动数据到文件"""
    blueprint_data_dir = verbose_dir / "blueprint_data"
    blueprint_data_dir.mkdir(parents=True, exist_ok=True)

    blueprint_file_path = blueprint_data_dir / f"{world.blueprint.name}.json"
    if blueprint_file_path.exists():
        return  # 如果文件已存在，则不覆盖

    # 保存 blueprint 数据到文件
    blueprint_file_path.write_text(world.blueprint.model_dump_json(), encoding="utf-8")


###############################################################################################################################################
def verbose_world_data(verbose_dir: Path, world: World) -> None:
    """保存世界数据到文件"""
    world_data_dir = verbose_dir / "world_data"
    world_data_dir.mkdir(parents=True, exist_ok=True)
    world_file_path = world_data_dir / f"{world.blueprint.name}.json"
    world_file_path.write_text(
        world.model_dump_json(), encoding="utf-8"
    )  # 保存 World 数据到文件，覆盖


###############################################################################################################################################
def verbose_player_session(verbose_dir: Path, player_session: PlayerSession) -> None:
    """保存玩家会话数据到文件"""
    player_session_dir = verbose_dir / "player_session"
    player_session_dir.mkdir(parents=True, exist_ok=True)

    player_session_file_path = player_session_dir / f"{player_session.name}.json"
    player_session_file_path.write_text(
        player_session.model_dump_json(), encoding="utf-8"
    )


###############################################################################################################################################
def verbose_entities_serialization(verbose_dir: Path, world: World) -> None:
    """保存实体快照到文件"""
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
def verbose_dungeon(verbose_dir: Path, dungeon: Dungeon) -> None:
    """保存地下城系统数据到文件"""
    dungeon_system_dir = verbose_dir / "dungeons"
    dungeon_system_dir.mkdir(parents=True, exist_ok=True)
    dungeon_system_path = dungeon_system_dir / f"{dungeon.name}.json"
    dungeon_system_path.write_text(dungeon.model_dump_json(), encoding="utf-8")


###############################################################################################################################################
