"""记忆标记登记表（`models/memory_tags.py`）的自检。

词表与代码必须双向对齐：
- 代码用到未登记标记 → `add_human_message` / `add_ai_message` 运行时断言（见 test_rpg_agent_memory）；
- 词表登记了没人用的标记 → 本测试的「词表腐烂」检查。
"""

import re
from pathlib import Path

from ai_rpg.models.memory_tags import MEMORY_TAGS

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def _all_source_text() -> str:
    """src 下全部 Python 源码（排除登记表自身）。"""
    chunks = [
        path.read_text(encoding="utf-8")
        for path in _SRC_ROOT.rglob("*.py")
        if path.name != "memory_tags.py"
    ]
    return "\n".join(chunks)


def test_no_unused_tag() -> None:
    """词表里的每个标记都要在代码里真的用到，避免登记表腐烂。"""
    source = _all_source_text()
    unused = sorted(
        tag
        for tag in MEMORY_TAGS
        if f'"{tag}"' not in source
        and f"{tag}=" not in source
        and f"{tag}:" not in source
    )
    assert not unused, f"这些标记已登记但没有任何调用点：{unused}"


def test_tags_are_identifier_friendly() -> None:
    """标记要能作为关键字参数名使用（`HumanMessage(**{tag: ...})` 与 `tag=...` 都要求）。"""
    bad = sorted(
        tag for tag in MEMORY_TAGS if not re.fullmatch(r"[a-z][a-z0-9_]*", tag)
    )
    assert not bad, f"标记名必须是 snake_case 标识符：{bad}"
