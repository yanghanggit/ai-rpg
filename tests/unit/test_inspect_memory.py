"""`scripts/inspect_memory.py`（只读审计工具）的单测。

工具本身没有运行时依赖（纯 stdlib + jsonl 文件），所以直接用临时快照目录驱动：
构造 `memories/{agent}.jsonl` 与 `entities/{agent}.json`，校验过滤、增量与压缩回退。
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from click.testing import CliRunner

from scripts.inspect_memory import (
    _agents_with_memory,
    _pile_changes,
    _short,
    main,
)


#######################################################################################################
def _write_memory(snapshot: Path, agent: str, messages: List[Dict[str, Any]]) -> None:
    path = snapshot / "memories" / f"{agent}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in messages) + "\n",
        encoding="utf-8",
    )


def _write_entity(snapshot: Path, agent: str, components: Dict[str, Any]) -> None:
    path = snapshot / "entities" / f"{agent}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(components, ensure_ascii=False), encoding="utf-8")


def _message(role: str, content: str, **tags: Any) -> Dict[str, Any]:
    return {"type": role, "content": content, "additional_kwargs": {}, **tags}


def _card(name: str) -> Dict[str, Any]:
    return {"name": name}


#######################################################################################################
class TestHelpers:
    def test_agents_with_memory_lists_jsonl_stems(self, tmp_path: Path) -> None:
        _write_memory(tmp_path, "角色.无名", [_message("human", "hi")])
        _write_memory(tmp_path, "怪物.野狗", [_message("human", "hi")])

        assert _agents_with_memory(tmp_path) == ["怪物.野狗", "角色.无名"]

    def test_agents_with_memory_on_missing_dir(self, tmp_path: Path) -> None:
        assert _agents_with_memory(tmp_path) == []

    def test_short_collapses_whitespace_and_truncates(self) -> None:
        assert _short("a\n  b\tc", 20) == "a b c"
        assert _short("x" * 10, 5) == "xxxx…"

    def test_pile_changes_reports_only_real_changes(self) -> None:
        prev = {"DeckComponent": {"cards": [_card("攻击")]}}
        cur = {"DeckComponent": {"cards": [_card("攻击"), _card("防守")]}}

        lines = _pile_changes(prev, cur)

        assert lines[0] == "DeckComponent.cards: 1 → 2"
        assert "防守" in lines[2]

    def test_pile_changes_ignores_missing_entity(self) -> None:
        assert _pile_changes(None, {"DeckComponent": {"cards": []}}) == []


#######################################################################################################
class TestCli:
    def test_prints_messages_and_piles(self, tmp_path: Path) -> None:
        _write_memory(
            tmp_path, "角色.无名", [_message("human", "第一条", agent_event="speak")]
        )
        _write_entity(
            tmp_path, "角色.无名", {"DeckComponent": {"cards": [_card("攻击")]}}
        )

        result = CliRunner().invoke(main, ["--snapshot", str(tmp_path)])

        assert result.exit_code == 0
        assert "第一条" in result.output
        assert "agent_event" in result.output  # 标记名要打印出来
        assert "DeckComponent.cards (1)" in result.output

    def test_tag_filter_keeps_only_matching_messages(self, tmp_path: Path) -> None:
        _write_memory(
            tmp_path,
            "角色.无名",
            [
                _message("human", "广播消息", broadcast_stage="场景.酒馆"),
                _message("human", "私发消息"),
            ],
        )

        result = CliRunner().invoke(
            main, ["--snapshot", str(tmp_path), "--tag", "broadcast_stage"]
        )

        assert result.exit_code == 0
        assert "广播消息" in result.output
        assert "私发消息" not in result.output

    def test_keyword_filter_keeps_only_matching_messages(self, tmp_path: Path) -> None:
        _write_memory(
            tmp_path,
            "角色.无名",
            [_message("human", "抽了三张"), _message("human", "过牌")],
        )

        result = CliRunner().invoke(
            main, ["--snapshot", str(tmp_path), "--keyword", "抽了"]
        )

        assert "抽了三张" in result.output
        assert "过牌" not in result.output

    def test_diff_prints_only_new_messages_and_pile_delta(self, tmp_path: Path) -> None:
        prev, cur = tmp_path / "prev", tmp_path / "cur"
        _write_memory(prev, "角色.无名", [_message("human", "旧消息")])
        _write_memory(
            cur, "角色.无名", [_message("human", "旧消息"), _message("human", "新消息")]
        )
        _write_entity(prev, "角色.无名", {"DeckComponent": {"cards": []}})
        _write_entity(cur, "角色.无名", {"DeckComponent": {"cards": [_card("攻击")]}})

        result = CliRunner().invoke(main, ["--snapshot", str(cur), "--diff", str(prev)])

        assert "新消息" in result.output
        assert "旧消息" not in result.output  # 增量模式不重复旧内容
        assert "DeckComponent.cards: 0 → 1" in result.output

    def test_diff_reports_no_change_in_one_line(self, tmp_path: Path) -> None:
        prev, cur = tmp_path / "prev", tmp_path / "cur"
        _write_memory(prev, "角色.无名", [_message("human", "消息")])
        _write_memory(cur, "角色.无名", [_message("human", "消息")])

        result = CliRunner().invoke(main, ["--snapshot", str(cur), "--diff", str(prev)])

        assert "角色.无名: 无变化" in result.output

    def test_diff_falls_back_to_full_dump_when_memory_shrinks(
        self, tmp_path: Path
    ) -> None:
        """记忆条数变少 = 发生压缩/重制，退回全量打印而不是算错增量。"""
        prev, cur = tmp_path / "prev", tmp_path / "cur"
        _write_memory(
            prev,
            "角色.无名",
            [_message("human", "一"), _message("human", "二"), _message("human", "三")],
        )
        _write_memory(cur, "角色.无名", [_message("human", "摘要")])

        result = CliRunner().invoke(main, ["--snapshot", str(cur), "--diff", str(prev)])

        assert "记忆条数变少" in result.output
        assert "摘要" in result.output

    def test_missing_snapshot_dir_fails_fast(self, tmp_path: Path) -> None:
        result = CliRunner().invoke(main, ["--snapshot", str(tmp_path / "nope")])

        assert result.exit_code != 0
