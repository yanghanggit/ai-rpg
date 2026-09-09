"""世界快照持久化模块（开发期留痕，非最终存储）。

将一次运行点的世界状态与玩家会话以明文目录树落盘，供开发者与 Agent
直接审阅、比对快照差异、判断运行状态。正式存储应使用数据库，本模块仅服务于开发期。
"""

import datetime
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, cast, List, Tuple

from loguru import logger
from pydantic import TypeAdapter

from ..models import (
    AgentMemory,
    Dungeon,
    PlayerSession,
    WorldState,
    get_buffer_string,
    Blueprint,
    ChatMessage,
    EntitySerialization,
    SessionMessage,
)

# TypeAdapter 用于将 JSON 字符串转换为 ChatMessage 对象
_message_adapter: TypeAdapter[ChatMessage] = TypeAdapter(ChatMessage)


###############################################################################################################################################
def restore_world(save_dir: Path) -> Tuple[WorldState, PlayerSession]:
    """从存档目录中读取并还原 WorldState 与 PlayerSession。

    Args:
        save_dir: 存档目录路径，即含有 world_state.json 与 player_session.jsonl 的目录
                      （例如 .worlds/{username}/{game}/{timestamp}/）

    Returns:
        (world, player_session) 元组

    Raises:
        FileNotFoundError: 若 world_state.json 或 player_session.jsonl 不存在
    """

    # 检查 save_dir 是否存在
    world_path = save_dir / "world_state.json"
    session_path = save_dir / "player_session.jsonl"

    # 检查文件是否存在
    if not world_path.exists():
        raise FileNotFoundError(f"找不到 world_state.json: {world_path}")

    # 检查 player_session.jsonl 是否存在
    if not session_path.exists():
        raise FileNotFoundError(f"找不到 player_session.jsonl: {session_path}")

    # 收集各子目录下待读取的文件清单
    def _files(sub: str, pattern: str) -> List[Path]:
        directory = save_dir / sub
        return sorted(directory.glob(pattern)) if directory.exists() else []

    memory_files = _files("memories", "*.jsonl")
    entity_files = _files("entities", "*.json")
    dungeon_files = _files("dungeon", "*.json")
    blueprint_files = _files("blueprint", "*.json")

    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    # 并行读文件（纯 I/O，文件相互独立）
    with ThreadPoolExecutor(max_workers=8) as executor:

        # 提交各类文件的读取任务到线程池
        world_future = executor.submit(_read, world_path)
        session_future = executor.submit(_read, session_path)

        # 并行读取 memories、entities、dungeon 和 blueprint 文件
        memory_raws = list(executor.map(_read, memory_files))
        entity_raws = list(executor.map(_read, entity_files))
        dungeon_raws = list(executor.map(_read, dungeon_files))
        blueprint_raws = list(executor.map(_read, blueprint_files))

        # 等待读取 world 和 session 文件的结果
        world_raw = world_future.result()

        # 等待读取 player_session 文件的结果
        session_raw = session_future.result()

    # 主线程反序列化 WorldState
    world = WorldState.model_validate_json(world_raw)

    # 从 memories/ 目录重建 agent_memories
    agent_memories: Dict[str, AgentMemory] = {}
    memories_dir = save_dir / "memories"
    for raw, memory_file in zip(memory_raws, memory_files):
        agent_name = memory_file.stem
        memory_messages: List[ChatMessage] = [
            _message_adapter.validate_json(line)
            for line in raw.strip().split("\n")
            if line.strip()
        ]
        agent_memories[agent_name] = AgentMemory(
            name=agent_name,
            messages=memory_messages,
            **_load_agent_memory_meta(memories_dir, agent_name),
        )

    # 将 agent_memories 赋值给 world 对象
    world.agent_memories = agent_memories

    # 从 entities/ 目录重建 entities
    world.entities = [
        EntitySerialization.model_validate_json(raw) for raw in entity_raws
    ]

    # 从 dungeon/ 目录重建 dungeon
    if dungeon_raws:
        world.dungeon = Dungeon.model_validate_json(dungeon_raws[0])

    # 从 blueprint/ 目录重建 blueprint
    if blueprint_raws:
        world.blueprint = Blueprint.model_validate_json(blueprint_raws[0])

    # 反序列化 PlayerSession（JSONL 格式：首行元数据，后续每行一个事件）
    lines = [line for line in session_raw.split("\n") if line.strip()]
    if not lines:
        raise ValueError(f"player_session.jsonl 为空: {session_path}")

    # 解析首行元数据
    meta = json.loads(lines[0])
    messages: List[SessionMessage] = [
        SessionMessage.model_validate_json(line) for line in lines[1:]
    ]

    # 创建 PlayerSession 对象
    player_session = PlayerSession(
        name=meta["name"],
        actor=meta["actor"],
        game=meta["game"],
        session_messages=messages,
        event_sequence=max((m.sequence_id for m in messages), default=0),
    )

    # 返回
    logger.debug(f"世界已还原: {save_dir}")
    return world, player_session


###############################################################################################################################################
def save_world(
    world: WorldState,
    player_session: PlayerSession,
    worlds_dir: Path,
    save_dir: Optional[Path] = None,
) -> bool:
    """保存游戏世界与玩家会话到存档目录。

    存档目录结构：
        {save_dir}/
            ├── world_state.json
            ├── player_session.jsonl    # JSONL 格式，首行为元数据，后续每行一个事件
            ├── blueprint/{blueprint_name}.json
            ├── entities/{entity}.json ...
            ├── memories/{agent}.jsonl, {agent}.meta.json, {agent}_buffer.txt ...
            ├── dungeon/{dungeon_name}.json
    """

    # 如果未指定 save_dir，则根据玩家名、游戏名和时间戳生成目录
    if save_dir is None:
        username = player_session.name
        game = str(world.blueprint.name)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        save_dir = worlds_dir / username / game / timestamp

    # 主线程集中完成 CPU 序列化，产出「相对路径 → 内容」清单
    files: List[Tuple[str, str]] = []

    # 保存 world_state.json 和 player_session.jsonl
    files.append(
        (
            "world_state.json",
            world.model_dump_json(
                exclude={"agent_memories", "entities", "dungeon", "blueprint"}
            ),
        )
    )

    # 保存 player_session.jsonl
    files.append(("player_session.jsonl", _build_session_jsonl(player_session)))

    # 保存实体数据
    for entity in world.entities:
        files.append((f"entities/{entity.name}.json", entity.model_dump_json()))

    # 保存代理记忆数据
    sep: str = "-" * 100
    for agent_name, agent_memory in world.agent_memories.items():

        # 正式存档数据
        message_lines = [msg.model_dump_json() for msg in agent_memory.messages]

        # 保存代理记忆的消息内容
        files.append((f"memories/{agent_name}.jsonl", "\n".join(message_lines) + "\n"))
        meta = agent_memory.model_dump(exclude={"name", "messages"})

        # 保存代理记忆的元数据
        files.append(
            (
                f"memories/{agent_name}.meta.json",
                json.dumps(meta, ensure_ascii=False),
            )
        )

        # 可读 buffer 调试产物
        buffer_str = get_buffer_string(
            agent_memory.messages,
            system_prefix="\n" + sep + "\nSystem",
            human_prefix="\n" + sep + "\nHuman",
            ai_prefix="\n" + sep + f"\nAI({agent_name})",
            tool_prefix="\n" + sep + f"\nTool({agent_name})",
        )

        # 保存代理记忆的可读 buffer
        files.append((f"memories/{agent_name}_buffer.txt", buffer_str))

    # 保存蓝图和地下城数据
    files.append(
        (f"blueprint/{world.blueprint.name}.json", world.blueprint.model_dump_json())
    )

    # 保存地下城数据
    files.append(
        (f"dungeon/{world.dungeon.name}.json", world.dungeon.model_dump_json())
    )

    # 先写临时目录，全部成功后原子替换为正式存档目录
    tmp_dir = save_dir.parent / f".{save_dir.name}.tmp-{os.getpid()}"
    shutil.rmtree(tmp_dir, ignore_errors=True)

    try:

        # 并行写文件（纯 I/O，文件相互独立）
        with ThreadPoolExecutor(max_workers=min(32, len(files))) as executor:

            # 提交所有文件写入任务
            futures = [
                executor.submit(_write_text, tmp_dir / rel_path, text)
                for rel_path, text in files
            ]

            # 等待所有文件写入完成
            for future in futures:
                future.result()  # 任一失败即抛异常

        # 原子替换正式存档目录
        if save_dir.exists():
            shutil.rmtree(save_dir)

        # 将临时目录替换为正式存档目录
        os.replace(tmp_dir, save_dir)

        logger.debug(f"存档成功: {save_dir}")
        return True

    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.error(f"存档失败: {e}")
        return False


###############################################################################################################################################
def _load_agent_memory_meta(memories_dir: Path, agent_name: str) -> Dict[str, Any]:
    """读取单个 agent 的记忆元数据（memories/{agent_name}.meta.json），缺失时返回空 dict。"""
    meta_path = memories_dir / f"{agent_name}.meta.json"
    if not meta_path.exists():
        return {}
    return cast(Dict[str, Any], json.loads(meta_path.read_text(encoding="utf-8")))


###############################################################################################################################################
def _build_session_jsonl(player_session: PlayerSession) -> str:
    """将 PlayerSession 序列化为 JSONL（首行元数据，后续每行一个事件）。"""
    lines = [
        json.dumps(
            {
                "name": player_session.name,
                "actor": player_session.actor,
                "game": player_session.game,
            },
            ensure_ascii=False,
        )
    ]
    lines.extend(msg.model_dump_json() for msg in player_session.session_messages)
    return "\n".join(lines) + "\n"


###############################################################################################################################################
def _write_text(path: Path, text: str) -> None:
    """写入单个文件，自动创建父目录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


###############################################################################################################################################
