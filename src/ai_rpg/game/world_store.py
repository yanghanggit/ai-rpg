"""世界存储模块

提供游戏世界数据的持久化与调试输出功能。

目录结构（persist_world_data）：
    {worlds_dir}/{username}/{game}/{timestamp}/
        ├── world.json              # World 快照（不含 agents_context）
        ├── player_session.jsonl    # JSONL，首行元数据，后续每行一个事件
        ├── entities/               # 各 ECS 实体单独一个 json
        ├── contexts/               # Agent LLM 对话上下文，每个 agent 一个 .jsonl
        ├── dungeon/                # 副本数据
        └── snapshot/               # (仅 enable_gzip=True)
            └── snapshot.zip        # 仅含 world.json + player_session.jsonl

主要功能：
    - 持久化游戏世界（persist_world_data）
    - 完整快照输出（dump_world_snapshot）
    - Agent 对话上下文输出（dump_agent_contexts）
    - ECS 实体序列化输出（dump_entities）
    - 副本数据输出（dump_dungeon）
    - 创建调试目录（ensure_debug_dir）
"""

import datetime
import json
import shutil
from typing import Optional, Tuple
import zipfile
from pathlib import Path
from pydantic import TypeAdapter
from ..models import get_buffer_string, AgentContext, PlayerSession, Dungeon, World
from ..models.messages import ContextMessage
from ..models.session_message import SessionMessage
from loguru import logger
from .config import WORLDS_DIR

_context_adapter: TypeAdapter[ContextMessage] = TypeAdapter(ContextMessage)


###############################################################################################################################################
def archive_world(
    world: World,
    player_session: PlayerSession,
    worlds_dir: Path = WORLDS_DIR,
    save_dir: Optional[Path] = None,
    enable_gzip: bool = False,
) -> bool:
    """持久化游戏世界数据到存档目录。

    存档目录结构：
        {save_dir}/
            ├── world.json
            ├── player_session.jsonl    # JSONL 格式，首行为元数据，后续每行一个事件
            ├── entities/{entity}.json ...
            ├── contexts/{agent}.jsonl, {agent}_buffer.txt ...
            ├── dungeon/{dungeon_name}.json
            └── snapshot/snapshot.zip   (仅 enable_gzip=True)

    Args:
        world: 世界对象（含蓝图）
        player_session: 玩家会话对象
        worlds_dir: 存档根目录，默认 WORLDS_DIR。仅 save_dir 为 None 时使用。
        save_dir: 显式指定存档目录。若为 None，则自动生成
                  {worlds_dir}/{username}/{game}/{timestamp}/
        enable_gzip: 为 True 时额外生成 snapshot/snapshot.zip，
                     内含 world.json + player_session.jsonl

    Returns:
        保存成功返回 True，失败返回 False
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

        # 将 world 序列化为 JSON（agents_context 已在 contexts/ 中独立存储）
        world_json = world.model_dump_json(exclude={"agents_context"})

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
        dump_entities(save_dir, world)

        # contexts/
        dump_agent_contexts(save_dir, world)

        # dungeon/
        dump_dungeon(save_dir, world.dungeon)

        # snapshot/snapshot.zip (optional)
        if enable_gzip:
            snapshot_dir = save_dir / "snapshot"
            snapshot_dir.mkdir(exist_ok=True)
            zip_path = snapshot_dir / "snapshot.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("world.json", world_json)
                zf.writestr("player_session.jsonl", player_session_jsonl)

        logger.debug(f"存档成功: {save_dir}")
        return True

    except Exception as e:
        logger.error(f"存档失败: {e}")
        return False


###############################################################################################################################################
def dump_world_snapshot(debug_dir: Path, world: World) -> None:

    # 写entities/目录
    dump_entities(debug_dir, world)

    # 写contexts/目录
    dump_agent_contexts(debug_dir, world)

    # 写dungeon/目录
    dump_dungeon(debug_dir, world.dungeon)


###############################################################################################################################################
def dump_agent_contexts(
    debug_dir: Path, world: World, should_write_buffer_string: bool = True
) -> None:

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
def dump_entities(debug_dir: Path, world: World) -> None:

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
def dump_dungeon(debug_dir: Path, dungeon: Dungeon) -> None:

    # 写dungeon/目录
    dungeon_dir = debug_dir / "dungeon"
    dungeon_dir.mkdir(parents=True, exist_ok=True)
    (dungeon_dir / f"{dungeon.name}.json").write_text(
        dungeon.model_dump_json(), encoding="utf-8"
    )


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
    world.agents_context = agents_context

    # 读取并反序列化 PlayerSession（JSONL 格式：首行元数据，后续每行一个事件）
    lines = session_path.read_text(encoding="utf-8").strip().split("\n")
    if not lines:
        raise ValueError(f"player_session.jsonl 为空: {session_path}")

    meta = json.loads(lines[0])
    messages: list[SessionMessage] = []
    for line in lines[1:]:
        if line.strip():
            messages.append(SessionMessage.model_validate_json(line))

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
