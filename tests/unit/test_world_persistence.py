"""针对 world_persistence.py 的单元测试。

覆盖 save_world / restore_world 的往返一致性、存档目录结构、
错误处理，以及临时目录 + 原子替换带来的失败安全性。
"""

import json
from pathlib import Path

import pytest

from src.ai_rpg.game import world_persistence
from src.ai_rpg.models import (
    AgentMemory,
    Blueprint,
    ComponentSerialization,
    Dungeon,
    EntitySerialization,
    PlayerSession,
    SpeakEvent,
    WorldState,
)
from src.ai_rpg.models.messages import AIMessage, HumanMessage


# ---------------------------------------------------------------------------
# 构造辅助
# ---------------------------------------------------------------------------


def _make_blueprint(name: str = "demo") -> Blueprint:
    return Blueprint(
        name=name,
        player_actor="hero",
        campaign_setting="setting",
        system_rules="",
        knowledge_base={},
        stages=[],
        world_entities=[],
    )


def _make_world(entity_counter: int = 1) -> WorldState:
    return WorldState(
        entity_counter=entity_counter,
        entities=[],
        dungeon=Dungeon(name="dungeon_a", rooms=[], profile=""),
        blueprint=_make_blueprint(),
        agent_memories={},
    )


def _make_player_session() -> PlayerSession:
    ps = PlayerSession(name="user", actor="hero", game="demo")
    ps.add_agent_event(
        SpeakEvent(
            message="m",
            actor="hero",
            stage="stage_1",
            target="npc",
            content="hello",
        )
    )
    return ps


# ---------------------------------------------------------------------------
# 往返一致性
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_basic_round_trip(self, tmp_path: Path) -> None:
        world = _make_world(entity_counter=7)
        save_dir = tmp_path / "snap"

        assert world_persistence.save_world(
            world, _make_player_session(), tmp_path, save_dir
        )

        restored_world, restored_session = world_persistence.restore_world(save_dir)

        assert restored_world.entity_counter == 7
        assert restored_world.blueprint.name == "demo"
        assert restored_world.dungeon.name == "dungeon_a"
        assert restored_session.name == "user"
        assert restored_session.actor == "hero"
        assert restored_session.game == "demo"

    def test_session_messages_round_trip(self, tmp_path: Path) -> None:
        save_dir = tmp_path / "snap"
        ps = _make_player_session()
        assert world_persistence.save_world(_make_world(), ps, tmp_path, save_dir)

        _, restored_session = world_persistence.restore_world(save_dir)

        assert restored_session.event_sequence == 1
        assert len(restored_session.session_messages) == 1
        msg = restored_session.session_messages[0]
        assert msg.sequence_id == 1
        assert isinstance(msg.agent_event, SpeakEvent)
        assert msg.agent_event.content == "hello"

    def test_agent_memories_round_trip(self, tmp_path: Path) -> None:
        world = _make_world()
        world.agent_memories["alice"] = AgentMemory(
            name="alice",
            messages=[HumanMessage(content="hi"), AIMessage(content="hello")],
            context_usage_ratio=0.42,
        )
        save_dir = tmp_path / "snap"
        assert world_persistence.save_world(
            world, _make_player_session(), tmp_path, save_dir
        )

        # 磁盘文件齐全
        assert (save_dir / "memories" / "alice.jsonl").exists()
        assert (save_dir / "memories" / "alice.meta.json").exists()
        assert (save_dir / "memories" / "alice_buffer.txt").exists()

        # buffer 为可读调试产物，含按 agent 名生成的 AI 前缀
        buffer = (save_dir / "memories" / "alice_buffer.txt").read_text(
            encoding="utf-8"
        )
        assert "AI(alice)" in buffer

        restored_world, _ = world_persistence.restore_world(save_dir)
        mem = restored_world.agent_memories["alice"]
        assert mem.context_usage_ratio == 0.42
        assert [m.content for m in mem.messages] == ["hi", "hello"]

    def test_entities_round_trip(self, tmp_path: Path) -> None:
        world = _make_world()
        world.entities = [
            EntitySerialization(
                name="goblin",
                components=[ComponentSerialization(name="stats", data={"hp": 10})],
            ),
            EntitySerialization(
                name="slime",
                components=[ComponentSerialization(name="stats", data={"hp": 3})],
            ),
        ]
        save_dir = tmp_path / "snap"
        assert world_persistence.save_world(
            world, _make_player_session(), tmp_path, save_dir
        )

        restored_world, _ = world_persistence.restore_world(save_dir)
        assert [e.name for e in restored_world.entities] == ["goblin", "slime"]
        assert restored_world.entities[0].components[0].data == {"hp": 10}

    def test_world_state_json_excludes_split_fields(self, tmp_path: Path) -> None:
        """world_state.json 应排除独立存储的字段。"""
        world = _make_world()
        world.agent_memories["alice"] = AgentMemory(name="alice", messages=[])
        save_dir = tmp_path / "snap"
        assert world_persistence.save_world(
            world, _make_player_session(), tmp_path, save_dir
        )

        data = json.loads((save_dir / "world_state.json").read_text(encoding="utf-8"))
        for key in ("agent_memories", "entities", "dungeon", "blueprint"):
            assert key not in data


# ---------------------------------------------------------------------------
# 错误处理
# ---------------------------------------------------------------------------


class TestRestoreErrors:
    def test_missing_world_state_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="world_state.json"):
            world_persistence.restore_world(tmp_path)

    def test_missing_player_session_raises(self, tmp_path: Path) -> None:
        save_dir = tmp_path / "snap"
        save_dir.mkdir()
        (save_dir / "world_state.json").write_text(
            _make_world().model_dump_json(
                exclude={"agent_memories", "entities", "dungeon", "blueprint"}
            ),
            encoding="utf-8",
        )
        with pytest.raises(FileNotFoundError, match="player_session.jsonl"):
            world_persistence.restore_world(save_dir)

    def test_empty_player_session_raises(self, tmp_path: Path) -> None:
        save_dir = tmp_path / "snap"
        save_dir.mkdir()
        (save_dir / "world_state.json").write_text(
            _make_world().model_dump_json(
                exclude={"agent_memories", "entities", "dungeon", "blueprint"}
            ),
            encoding="utf-8",
        )
        (save_dir / "player_session.jsonl").write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="为空"):
            world_persistence.restore_world(save_dir)


# ---------------------------------------------------------------------------
# 临时目录 + 原子替换
# ---------------------------------------------------------------------------


class TestAtomicSave:
    def test_failure_returns_false_and_leaves_no_partial(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        save_dir = tmp_path / "snap"
        real_write = world_persistence._write_text

        def failing_write(path: Path, text: str) -> None:
            if path.name == "dungeon_a.json":
                raise OSError("simulated write failure")
            real_write(path, text)

        monkeypatch.setattr(world_persistence, "_write_text", failing_write)

        assert (
            world_persistence.save_world(
                _make_world(), _make_player_session(), tmp_path, save_dir
            )
            is False
        )
        assert not save_dir.exists()
        assert not [p for p in tmp_path.iterdir() if ".tmp-" in p.name]

    def test_failure_preserves_existing_save(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        save_dir = tmp_path / "snap"
        assert world_persistence.save_world(
            _make_world(entity_counter=1), _make_player_session(), tmp_path, save_dir
        )

        real_write = world_persistence._write_text

        def failing_write(path: Path, text: str) -> None:
            if path.name == "dungeon_a.json":
                raise OSError("simulated write failure")
            real_write(path, text)

        monkeypatch.setattr(world_persistence, "_write_text", failing_write)

        assert (
            world_persistence.save_world(
                _make_world(entity_counter=2),
                _make_player_session(),
                tmp_path,
                save_dir,
            )
            is False
        )

        # 旧存档应保持不变
        restored_world, _ = world_persistence.restore_world(save_dir)
        assert restored_world.entity_counter == 1

    def test_overwrite_replaces_cleanly(self, tmp_path: Path) -> None:
        save_dir = tmp_path / "snap"

        world1 = _make_world()
        world1.agent_memories["alice"] = AgentMemory(name="alice", messages=[])
        assert world_persistence.save_world(
            world1, _make_player_session(), tmp_path, save_dir
        )

        world2 = _make_world()
        world2.agent_memories["bob"] = AgentMemory(name="bob", messages=[])
        assert world_persistence.save_world(
            world2, _make_player_session(), tmp_path, save_dir
        )

        restored_world, _ = world_persistence.restore_world(save_dir)
        assert set(restored_world.agent_memories.keys()) == {"bob"}
        assert not (save_dir / "memories" / "alice.jsonl").exists()

    def test_auto_generated_save_dir(self, tmp_path: Path) -> None:
        world = _make_world()  # blueprint.name == "demo"
        ps = _make_player_session()  # name == "user"

        assert world_persistence.save_world(world, ps, worlds_dir=tmp_path)

        game_dir = tmp_path / "user" / "demo"
        assert game_dir.exists()
        snapshots = [p for p in game_dir.iterdir() if p.is_dir()]
        assert len(snapshots) == 1
        assert (snapshots[0] / "world_state.json").exists()

        restored_world, restored_session = world_persistence.restore_world(snapshots[0])
        assert restored_world.entity_counter == 1
        assert restored_session.name == "user"
