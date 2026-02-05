"""世界调试模块

提供游戏世界数据的调试和详细日志输出功能。

主要功能：
- 创建调试日志目录（ensure_debug_dir）
- 保存完整的游戏状态快照（dump_world_snapshot）
- 保存代理对话上下文（dump_agent_contexts）
- 保存实体序列化数据（dump_entities）
- 保存地下城数据（dump_dungeon）
"""

import shutil
from pathlib import Path
from langchain_core.messages import get_buffer_string
from ..models import World, Dungeon


###############################################################################################################################################
def ensure_debug_dir(base_dir: Path, player_session_name: str, game_name: str) -> Path:
    """创建并返回调试日志目录

    Args:
        base_dir: 基础日志目录
        player_session_name: 玩家会话名称
        game_name: 游戏名称

    Returns:
        Path: 调试目录路径
    """
    dir = base_dir / f"{player_session_name}" / f"{game_name}"
    if not dir.exists():
        dir.mkdir(parents=True, exist_ok=True)
    assert dir.exists()
    assert dir.is_dir()
    return dir


###############################################################################################################################################
def dump_world_snapshot(debug_dir: Path, world: World) -> None:
    """保存完整的游戏状态快照

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
    """保存代理对话上下文

    Args:
        debug_dir: 调试目录路径
        world: 世界对象
        should_write_buffer_string: 是否保存可读文本格式，默认 True
    """
    context_dir = debug_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    for agent_name, agent_context in world.agents_context.items():
        context_path = context_dir / f"{agent_name}.json"
        context_path.write_text(agent_context.model_dump_json(), encoding="utf-8")

        if should_write_buffer_string:

            buffer_str = get_buffer_string(
                agent_context.context,
                human_prefix=f"""\nHuman""",
                ai_prefix=f"""\nAI({agent_name})""",
            )
            context_path2 = context_dir / f"{agent_name}_buffer.txt"
            context_path2.write_text(buffer_str, encoding="utf-8")


###############################################################################################################################################
def dump_entities(debug_dir: Path, world: World) -> None:
    """保存所有实体序列化数据

    Args:
        debug_dir: 调试目录路径
        world: 世界对象
    """
    entities_serialization_dir = debug_dir / "entities_serialization"
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
def dump_dungeon(debug_dir: Path, dungeon: Dungeon) -> None:
    """保存地下城数据

    Args:
        debug_dir: 调试目录路径
        dungeon: 地下城对象
    """
    dungeon_system_dir = debug_dir / "dungeons"
    dungeon_system_dir.mkdir(parents=True, exist_ok=True)
    dungeon_system_path = dungeon_system_dir / f"{dungeon.name}.json"
    dungeon_system_path.write_text(dungeon.model_dump_json(), encoding="utf-8")


###############################################################################################################################################
