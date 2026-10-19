#!/usr/bin/env python3
"""审计某个快照里 agent 的 LLM 记忆与牌堆状态（只读，无外部依赖）。

为什么需要它：牌堆之间的**静默流转**（抽牌、弃牌、回合末清手牌、retain 归还、
战斗结束拆除）不写 LLM 记忆，`.chat_dumps` 也看不到。要回答「这次动作为谁写了
记忆」「哪条堆变了多少」，需要对账两侧：`memories/{agent}.jsonl`（记忆）与
`entities/{agent}.json`（四条牌堆组件）。`--diff` 直接把两侧的增量列出来。

用法:
  # 某个 agent 的记忆 + 牌堆
  uv run python -m scripts.inspect_memory --snapshot .worlds/e2e/Game1/2026-... --agent 角色.无名

  # 全部有记忆文件的 agent（快速扫一遍谁被写了消息）
  uv run python -m scripts.inspect_memory --snapshot .worlds/e2e/Game1/2026-...

  # 与上一个快照对账：只列新增记忆 + 各堆数量/内容变化
  uv run python -m scripts.inspect_memory --snapshot <新> --diff <旧> --agent 角色.无名

  # 只看含关键词的消息
  uv run python -m scripts.inspect_memory --snapshot <快照> --agent 怪物.野狗 --keyword 手牌
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click

# 牌堆组件 → 字段（顺序即打印顺序；None 表示只关心该组件是否存在）
PILE_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("DeckComponent", "cards"),
    ("DrawPileComponent", "cards"),
    ("DrawPileComponent", "retained_cards"),
    ("HandComponent", "cards"),
    ("DiscardPileComponent", "cards"),
    ("ExhaustPileComponent", "cards"),
    ("SpoilsComponent", "candidate_cards"),
    ("SpoilsComponent", "claimed_cards"),
)


#######################################################################################################
def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """读取 jsonl 消息文件；文件不存在时返回空列表。"""
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _load_entity(snapshot: Path, agent: str) -> Optional[Dict[str, Any]]:
    """读取实体快照（components 以组件类型名为键）；不存在时返回 None。"""
    path = snapshot / "entities" / f"{agent}.json"
    if not path.exists():
        return None
    loaded: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _agents_with_memory(snapshot: Path) -> List[str]:
    """列出该快照里有记忆文件的 agent 名。"""
    memories_dir = snapshot / "memories"
    if not memories_dir.exists():
        return []
    return sorted(p.stem for p in memories_dir.glob("*.jsonl"))


def _short(text: str, width: int) -> str:
    """压成单行并截断，便于表格化阅读。"""
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _card_names(entity: Dict[str, Any], component: str, field: str) -> List[str]:
    """取某个组件字段里的卡牌名列表；组件/字段缺失时返回空列表。"""
    comp = entity.get(component)
    if not isinstance(comp, dict):
        return []
    cards = comp.get(field) or []
    return [card.get("name", "?") for card in cards]


def _format_piles(entity: Dict[str, Any]) -> List[str]:
    """把牌堆状态渲染成若干行（空堆也打印，方便对账时看到“归零”）。"""
    lines: List[str] = []
    for component, field in PILE_FIELDS:
        if component not in entity:
            continue
        names = _card_names(entity, component, field)
        lines.append(f"{component}.{field} ({len(names)}): {names}")

    round_stats = entity.get("RoundStatsComponent")
    if isinstance(round_stats, dict) and "energy" in round_stats:
        lines.append(f"energy={round_stats['energy']}")
    return lines


def _print_messages(
    rows: List[Dict[str, Any]],
    *,
    start: int,
    width: int,
    keyword: str,
) -> None:
    """打印记忆消息：序号、类型、结构化附属字段名、正文。"""
    for index, row in enumerate(rows):
        if index < start:
            continue
        role = row.get("type") or row.get("role") or "?"
        content = row.get("content") or ""
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        if keyword and keyword not in content:
            continue
        extras = sorted(
            key
            for key in row.keys()
            if key not in {"type", "role", "content"} and row.get(key) is not None
        )
        print(f"[{index:03d}] {role:<12} extra={extras}")
        for line in content.splitlines():
            if line.strip():
                print(f"      {_short(line, width)}")


def _pile_changes(
    prev_entity: Optional[Dict[str, Any]], entity: Optional[Dict[str, Any]]
) -> List[str]:
    """对比前后两个实体快照的牌堆内容，返回变化描述行（无变化时返回空列表）。"""
    if prev_entity is None or entity is None:
        return []
    lines: List[str] = []
    for component, field in PILE_FIELDS:
        if component not in entity and component not in prev_entity:
            continue
        before = _card_names(prev_entity, component, field)
        after = _card_names(entity, component, field)
        if before == after:
            continue
        lines.append(f"{component}.{field}: {len(before)} → {len(after)}")
        lines.append(f"    旧: {before}")
        lines.append(f"    新: {after}")
    return lines


def _report(
    snapshot: Path,
    agent: str,
    *,
    prev: Optional[Path],
    width: int,
    keyword: str,
) -> None:
    """打印单个 agent 的记忆与牌堆状态（给出 prev 时只展示增量）。"""
    rows = _load_jsonl(snapshot / "memories" / f"{agent}.jsonl")
    prev_rows = _load_jsonl(prev / "memories" / f"{agent}.jsonl") if prev else []
    entity = _load_entity(snapshot, agent)
    prev_entity = _load_entity(prev, agent) if prev else None

    # 前缀基线：上一条记忆的长度即本地新增消息的起点；变短说明被压缩/重制，退回全量。
    baseline = 0
    reset_notice = ""
    if prev is not None:
        if len(rows) >= len(prev_rows):
            baseline = len(prev_rows)
        else:
            reset_notice = "（记忆条数变少：可能发生压缩/重制，下面打印全量）"

    changes = _pile_changes(prev_entity, entity)
    has_new_messages = len(rows) > baseline

    # 对账模式下，没有新增记忆也没有牌堆变化就只报一行，不刷空白段。
    if prev is not None and not has_new_messages and not changes and not reset_notice:
        if not keyword:
            print(f"{agent}: 无变化")
        return

    print(f"\n=== 记忆 · {agent} ===")
    if prev is not None:
        print(f"消息条数: {len(rows)}（相对上一快照 {len(rows) - len(prev_rows):+d}）")
    else:
        print(f"消息条数: {len(rows)}")
    if reset_notice:
        print(reset_notice)
    _print_messages(rows, start=baseline, width=width, keyword=keyword)

    if entity is None:
        print(f"\n（无实体文件：{snapshot / 'entities' / f'{agent}.json'}）")
        return

    print(f"\n=== 牌堆 · {agent} ===")
    for line in _format_piles(entity):
        print(line)

    if prev is None:
        return
    print("\n=== 牌堆变化（相对上一快照）===")
    if not changes:
        print("（无变化）")
        return
    for line in changes:
        print(line)


#######################################################################################################
@click.command()
@click.option(
    "--snapshot", "snapshot", type=str, required=True, help="存档目录（.worlds/...）"
)
@click.option(
    "--agent",
    "agents",
    type=str,
    multiple=True,
    help="agent 实体全名（可重复）；缺省打印所有有记忆文件的 agent",
)
@click.option(
    "--diff",
    "prev_snapshot",
    type=str,
    default=None,
    help="与之对账的上一个快照目录：只列新增记忆与牌堆变化",
)
@click.option("--width", "width", type=int, default=120, help="每条消息截断宽度")
@click.option(
    "--keyword", "keyword", type=str, default="", help="只显示含该关键词的消息"
)
def main(
    snapshot: str,
    agents: Tuple[str, ...],
    prev_snapshot: Optional[str],
    width: int,
    keyword: str,
) -> None:
    root = Path(snapshot)
    assert root.is_dir(), f"快照目录不存在: {root}"
    prev = Path(prev_snapshot) if prev_snapshot else None
    if prev is not None:
        assert prev.is_dir(), f"对账快照目录不存在: {prev}"

    targets = list(agents) or sorted(
        set(_agents_with_memory(root))
        | set(_agents_with_memory(prev) if prev else set())
    )
    assert targets, f"该快照下没有可审计的 agent: {root}"

    for agent in targets:
        _report(root, agent, prev=prev, width=width, keyword=keyword)
    print()


if __name__ == "__main__":
    main()
