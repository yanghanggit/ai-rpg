"""记忆标记登记表（`models/memory_tags.py`）的自检。

词表与代码必须双向对齐：
- 代码用到未登记标记 → `add_human_message` / `add_ai_message` 运行时断言（见 test_rpg_agent_memory）；
- 词表登记了没人用的标记 → 本测试的「词表腐烂」检查。
"""

import re
from pathlib import Path
from typing import Dict, List, Set

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


_ALLOWED_DECLARED = {"content", "additional_kwargs", "type", "tool_call_id"}
_MESSAGE_CTORS = ("HumanMessage", "AIMessage", "ToolMessage", "SystemMessage")


def _top_level_kwargs(body: str) -> List[str]:
    """取构造参数体里**顶层**的 kwarg 名（忽略嵌套调用/容器的内部关键字）。"""
    keys: List[str] = []
    depth = 0
    for match in re.finditer(r"[\(\[\{\)\]\}]|[a-zA-Z_]\w*\s*=(?!=)", body):
        token = match.group(0)
        if token in "([{":
            depth += 1
        elif token in ")]}":
            depth -= 1
        elif depth == 0:
            keys.append(token.split("=")[0].strip())
    return keys


def test_message_kwargs_are_registered_tags() -> None:
    """静态闸门：消息构造处的顶层关键字必须是已登记标记。

    运行时校验（`add_human_message`）只能覆盖真的跑到的路径；本测试覆盖全部构造点，
    避免新写的标记只在没被测到的分支里静默失效。
    """
    unregistered: Dict[str, Set[str]] = {}
    for path in _SRC_ROOT.rglob("*.py"):
        if path.name in ("memory_tags.py", "messages.py"):
            continue
        text = path.read_text(encoding="utf-8")
        for ctor in _MESSAGE_CTORS:
            for match in re.finditer(rf"\b{ctor}\(", text):
                start = match.end() - 1
                depth = 0
                end = None
                for index in range(start, len(text)):
                    if text[index] == "(":
                        depth += 1
                    elif text[index] == ")":
                        depth -= 1
                        if depth == 0:
                            end = index
                            break
                assert end is not None, f"{path}: 未闭合的消息构造 {ctor}("
                for key in _top_level_kwargs(text[start + 1 : end]):
                    if key in _ALLOWED_DECLARED or key in MEMORY_TAGS:
                        continue
                    unregistered.setdefault(key, set()).add(path.name)

    assert not unregistered, f"这些关键字未在 memory_tags.py 登记：{unregistered}"
