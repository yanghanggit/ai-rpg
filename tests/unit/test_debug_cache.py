"""针对 debug_cache.py 的单元测试。"""

from collections.abc import Iterator
from pathlib import Path
from typing import List
from unittest.mock import patch
import pytest
from src.ai_rpg.models.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from src.ai_rpg.models.messages import ContextMessage
from src.ai_rpg.utils.debug_cache import (
    compute_cache_key,
    load_debug_cache,
    save_debug_cache,
)


# ---------------------------------------------------------------------------
# compute_cache_key
# ---------------------------------------------------------------------------


class TestComputeCacheKey:
    def test_returns_64_char_hex(self) -> None:
        key = compute_cache_key([HumanMessage(content="hello")])
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_deterministic(self) -> None:
        ctx: List[ContextMessage] = [
            SystemMessage(content="sys"),
            HumanMessage(content="hi"),
        ]
        assert compute_cache_key(ctx) == compute_cache_key(ctx)

    def test_different_content_different_key(self) -> None:
        key1 = compute_cache_key([HumanMessage(content="a")])
        key2 = compute_cache_key([HumanMessage(content="b")])
        assert key1 != key2

    def test_different_order_different_key(self) -> None:
        key1 = compute_cache_key([HumanMessage(content="x"), AIMessage(content="y")])
        key2 = compute_cache_key([AIMessage(content="y"), HumanMessage(content="x")])
        assert key1 != key2

    def test_empty_context(self) -> None:
        key = compute_cache_key([])
        assert len(key) == 64


# ---------------------------------------------------------------------------
# save / load round-trip（通过 tmp_path 隔离文件系统）
# ---------------------------------------------------------------------------


class TestSaveLoadRoundTrip:
    @pytest.fixture(autouse=True)
    def _patch_cache_dir(self, tmp_path: Path) -> Iterator[None]:
        with patch("src.ai_rpg.utils.debug_cache.DEBUG_CACHE_DIR", tmp_path):
            yield

    def test_load_miss_returns_none(self) -> None:
        assert load_debug_cache("nonexistent_key") is None

    def test_round_trip_ai_message(self) -> None:
        msg = AIMessage(content="AI 回复")
        key = "test_ai"
        save_debug_cache(key, msg)
        result = load_debug_cache(key)
        assert isinstance(result, AIMessage)
        assert result.content == "AI 回复"

    def test_round_trip_human_message(self) -> None:
        msg = HumanMessage(content="用户输入")
        key = "test_human"
        save_debug_cache(key, msg)
        result = load_debug_cache(key)
        assert isinstance(result, HumanMessage)
        assert result.content == "用户输入"

    def test_round_trip_system_message(self) -> None:
        msg = SystemMessage(content="系统提示")
        key = "test_system"
        save_debug_cache(key, msg)
        result = load_debug_cache(key)
        assert isinstance(result, SystemMessage)
        assert result.content == "系统提示"

    def test_round_trip_tool_message(self) -> None:
        msg = ToolMessage(content="工具结果", tool_call_id="call_abc")
        key = "test_tool"
        save_debug_cache(key, msg)
        result = load_debug_cache(key)
        assert isinstance(result, ToolMessage)
        assert result.content == "工具结果"
        assert result.tool_call_id == "call_abc"

    def test_corrupt_file_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "bad_key.json").write_text("not valid json", encoding="utf-8")
        assert load_debug_cache("bad_key") is None

    def test_saved_file_is_flat_json(self, tmp_path: Path) -> None:
        """存储格式应为扁平 JSON，无外层包装。"""
        msg = AIMessage(content="test")
        save_debug_cache("flat", msg)
        import json

        data = json.loads((tmp_path / "flat.json").read_text(encoding="utf-8"))
        assert data.get("type") == "ai"
        assert data.get("content") == "test"
        assert "ai_messages" not in data
