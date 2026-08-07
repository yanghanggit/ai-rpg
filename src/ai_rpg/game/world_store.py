"""世界存储模块
提供游戏世界数据的持久化与调试输出功能。
"""

import datetime
import json
import shutil
from typing import Optional, Tuple
from pathlib import Path
from pydantic import TypeAdapter
from ..models import get_buffer_string, AgentContext, PlayerSession, Dungeon, World
from ..models.blueprint import Blueprint
from ..models.messages import ContextMessage
from ..models.serialization import EntitySerialization
from ..models.session_message import SessionMessage
from loguru import logger

# TypeAdapter 用于将 JSON 字符串转换为 ContextMessage 对象
_context_adapter: TypeAdapter[ContextMessage] = TypeAdapter(ContextMessage)


###############################################################################################################################################
def restore_world(snapshot_dir: Path) -> Tuple[World, PlayerSession]:
    """从存档目录中读取并还原 World 与 PlayerSession。

    Args:
        snapshot_dir: 存档目录路径，即含有 world.json 与 player_session.jsonl 的目录
                      （例如 .worlds/{username}/{game}/{timestamp}/）

    Returns:
        (world, player_session) 元组

    Raises:
        FileNotFoundError: 若 world.json 或 player_session.jsonl 不存在
    """

    # 检查 snapshot_dir 是否存在
    world_path = snapshot_dir / "world.json"
    session_path = snapshot_dir / "player_session.jsonl"

    # 检查文件是否存在
    if not world_path.exists():
        raise FileNotFoundError(f"找不到 world.json: {world_path}")

    # 检查 player_session.jsonl 是否存在
    if not session_path.exists():
        raise FileNotFoundError(f"找不到 player_session.jsonl: {session_path}")

    # 读取并反序列化 World
    world = World.model_validate_json(world_path.read_text(encoding="utf-8"))

    # 从 contexts/ 目录重建 agents_context
    agents_context: dict[str, AgentContext] = {}
    contexts_dir = snapshot_dir / "contexts"
    if contexts_dir.exists():
        for ctx_file in contexts_dir.glob("*.jsonl"):
            agent_name = ctx_file.stem
            context_messages: list[ContextMessage] = []
            for line in ctx_file.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    context_messages.append(_context_adapter.validate_json(line))
            agents_context[agent_name] = AgentContext(
                name=agent_name, context=context_messages
            )

    # 将 agents_context 赋值给 world
    world.agents_context = agents_context

    # 从 entities/ 目录重建 entities
    entities_list: list[EntitySerialization] = []
    entities_dir = snapshot_dir / "entities"
    if entities_dir.exists():
        for ent_file in entities_dir.glob("*.json"):
            entities_list.append(
                EntitySerialization.model_validate_json(
                    ent_file.read_text(encoding="utf-8")
                )
            )

    # 将 entities_list 赋值给 world.entities
    world.entities = entities_list

    # 从 dungeon/ 目录重建 dungeon
    dungeon_dir = snapshot_dir / "dungeon"
    if dungeon_dir.exists():
        for dun_file in dungeon_dir.glob("*.json"):
            world.dungeon = Dungeon.model_validate_json(
                dun_file.read_text(encoding="utf-8")
            )
            break

    # 从 blueprint/ 目录重建 blueprint
    blueprint_dir = snapshot_dir / "blueprint"
    if blueprint_dir.exists():
        for bp_file in blueprint_dir.glob("*.json"):
            world.blueprint = Blueprint.model_validate_json(
                bp_file.read_text(encoding="utf-8")
            )
            break

    # 读取并反序列化 PlayerSession（JSONL 格式：首行元数据，后续每行一个事件）
    lines = session_path.read_text(encoding="utf-8").strip().split("\n")
    if not lines:
        raise ValueError(f"player_session.jsonl 为空: {session_path}")

    # 解析首行元数据
    meta = json.loads(lines[0])
    messages: list[SessionMessage] = []
    for line in lines[1:]:
        if line.strip():
            messages.append(SessionMessage.model_validate_json(line))

    # 创建 PlayerSession 对象
    player_session = PlayerSession(
        name=meta["name"],
        actor=meta["actor"],
        game=meta["game"],
        session_messages=messages,
        event_sequence=max((m.sequence_id for m in messages), default=0),
    )

    # 返回
    logger.debug(f"世界已还原: {snapshot_dir}")
    return world, player_session


###############################################################################################################################################
def archive_world(
    world: World,
    player_session: PlayerSession,
    worlds_dir: Path,
    save_dir: Optional[Path] = None,
) -> bool:
    """持久化游戏世界数据到存档目录。

    存档目录结构：
        {save_dir}/
            ├── world.json
            ├── player_session.jsonl    # JSONL 格式，首行为元数据，后续每行一个事件
            ├── blueprint/{blueprint_name}.json
            ├── entities/{entity}.json ...
            ├── contexts/{agent}.jsonl, {agent}_buffer.txt ...
            ├── dungeon/{dungeon_name}.json
    """

    # 如果未指定 save_dir，则根据玩家名、游戏名和时间戳生成目录
    if save_dir is None:
        username = player_session.name
        game = str(world.blueprint.name)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        save_dir = worlds_dir / username / game / timestamp

    # 创建存档目录
    save_dir.mkdir(parents=True, exist_ok=True)

    try:

        # 将 world 序列化为 JSON（各字段已在独立目录中存储）
        world_json = world.model_dump_json(
            exclude={"agents_context", "entities", "dungeon", "blueprint"}
        )

        # player_session 序列化为 JSONL（首行元数据，后续每行一个事件）
        session_lines = [
            json.dumps(
                {
                    "name": player_session.name,
                    "actor": player_session.actor,
                    "game": player_session.game,
                },
                ensure_ascii=False,
            )
        ]
        for msg in player_session.session_messages:
            session_lines.append(msg.model_dump_json())
        player_session_jsonl = "\n".join(session_lines) + "\n"

        # world.json
        (save_dir / "world.json").write_text(world_json, encoding="utf-8")

        # player_session.jsonl
        (save_dir / "player_session.jsonl").write_text(
            player_session_jsonl, encoding="utf-8"
        )

        # entities/
        _dump_entities(save_dir, world)

        # contexts/
        _dump_agent_contexts(save_dir, world)

        # blueprint/
        _dump_blueprint(save_dir, world.blueprint)

        # dungeon/
        _dump_dungeon(save_dir, world.dungeon)

        logger.debug(f"存档成功: {save_dir}")
        return True

    except Exception as e:
        logger.error(f"存档失败: {e}")
        return False


###############################################################################################################################################
def _dump_agent_contexts(
    debug_dir: Path, world: World, should_write_buffer_string: bool = True
) -> None:
    """写入每个 agent 的上下文 JSONL 和 buffer.txt 文件到 contexts/ 目录"""

    # 写contexts/目录
    context_dir = debug_dir / "contexts"
    context_dir.mkdir(parents=True, exist_ok=True)

    # 写每个 agent 的上下文 JSONL 和 buffer.txt
    for agent_name, agent_context in world.agents_context.items():

        # 写 agent_name.jsonl（每行一条消息）
        context_lines = [msg.model_dump_json() for msg in agent_context.context]
        (context_dir / f"{agent_name}.jsonl").write_text(
            "\n".join(context_lines) + "\n", encoding="utf-8"
        )

        # 写 agent_name_buffer.txt
        if should_write_buffer_string:
            buffer_str = get_buffer_string(
                agent_context.context,
                system_prefix="\n" + "-" * 86 + "\nSystem",
                human_prefix="\n" + "-" * 86 + "\nHuman",
                ai_prefix="\n" + "-" * 86 + f"\nAI({agent_name})",
                tool_prefix="\n" + "-" * 86 + f"\nTool({agent_name})",
            )
            (context_dir / f"{agent_name}_buffer.txt").write_text(
                buffer_str, encoding="utf-8"
            )


###############################################################################################################################################
def _dump_entities(debug_dir: Path, world: World) -> None:
    """写入每个实体的 JSON 文件到 entities/ 目录"""

    # 写entities/目录
    entities_dir = debug_dir / "entities"
    if entities_dir.exists():
        shutil.rmtree(entities_dir)

    # 创建 entities/ 目录
    entities_dir.mkdir(parents=True, exist_ok=True)

    # 写每个实体的 JSON 文件
    for entity_serialization in world.entities:
        path = entities_dir / f"{entity_serialization.name}.json"
        path.write_text(entity_serialization.model_dump_json(), encoding="utf-8")


###############################################################################################################################################
def _dump_dungeon(debug_dir: Path, dungeon: Dungeon) -> None:
    """写入 dungeon 的 JSON 文件到 dungeon/ 目录"""

    # 写dungeon/目录
    dungeon_dir = debug_dir / "dungeon"
    dungeon_dir.mkdir(parents=True, exist_ok=True)
    (dungeon_dir / f"{dungeon.name}.json").write_text(
        dungeon.model_dump_json(), encoding="utf-8"
    )


###############################################################################################################################################
def _dump_blueprint(debug_dir: Path, blueprint: Blueprint) -> None:
    """写入 blueprint 的 JSON 文件到 blueprint/ 目录"""

    # 写blueprint/目录
    blueprint_dir = debug_dir / "blueprint"
    blueprint_dir.mkdir(parents=True, exist_ok=True)
    (blueprint_dir / f"{blueprint.name}.json").write_text(
        blueprint.model_dump_json(), encoding="utf-8"
    )


###############################################################################################################################################
