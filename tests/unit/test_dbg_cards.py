"""`dbg_game_agent.cards` 单测：显式候选规格的解析（id / 槽位 / 关键词 / 补足）。

只测纯逻辑：原型库索引由用例直接构造，槽位查询按 id 打桩，不碰数据库。
"""

from typing import Dict, List, Optional

import pytest

from ai_rpg.dbg_game_agent import cards as cards_module
from ai_rpg.dbg_game_agent.cards import (
    filter_entries,
    resolve_candidate_ids,
    resolve_prototype_ids,
)
from ai_rpg.pgsql import CardPrototypeIndexEntry


def _entry(
    prototype_id: str,
    *,
    name: str = "",
    summary: str = "",
    archetype: str = "攻击端",
    archetype_subtype: str = "前端伤害",
    keywords: Optional[List[str]] = None,
    card_type: str = "手牌",
    tier: str = "basic",
) -> CardPrototypeIndexEntry:
    return {
        "prototype_id": prototype_id,
        "card_type": card_type,
        "tier": tier,
        "archetype": archetype,
        "archetype_subtype": archetype_subtype,
        "name": name or prototype_id,
        "summary": summary,
        "keywords": keywords or [],
    }


_INDEX: List[CardPrototypeIndexEntry] = [
    _entry("proto.attack", name="基础攻击", keywords=["damage", "single"]),
    _entry(
        "proto.summon",
        name="召唤兽",
        summary="抓到即召唤、retain 常驻",
        archetype_subtype="自主运行",
        keywords=["on_autonomous_affixes", "autonomous"],
    ),
    _entry(
        "proto.burst",
        name="一次性爆发",
        keywords=["exhaust"],
    ),
]

# id → 开放的词缀槽（模拟 card_json 解析结果）
_SLOTS: Dict[str, List[str]] = {
    "proto.attack": [],
    "proto.summon": ["on_autonomous_affixes"],
    "proto.burst": ["on_play_affixes"],
}


@pytest.fixture(autouse=True)
def _stub_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    """槽位查询打桩：只暴露 _SLOTS 里的映射，避免读数据库。"""
    monkeypatch.setattr(
        cards_module, "prototype_slots", lambda prototype_id: _SLOTS[prototype_id]
    )


#######################################################################################################################################
def test_resolve_explicit_ids_keeps_order_and_duplicates() -> None:
    """显式 id 照给：顺序保留、允许重复（与牌库路径语义一致）。"""
    resolved = resolve_prototype_ids(
        prototype_ids=["proto.summon", "proto.burst", "proto.summon"],
        index=_INDEX,
    )

    assert resolved == ["proto.summon", "proto.burst", "proto.summon"]


def test_resolve_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="未知的 手牌 原型 id"):
        resolve_prototype_ids(prototype_ids=["proto.nope"], index=_INDEX)


def test_resolve_rejects_id_of_other_card_type() -> None:
    """装备原型不能塞进手牌奖励：索引按 card_type 过滤后就是未知 id。"""
    with pytest.raises(ValueError, match="未知的 手牌 原型 id"):
        resolve_prototype_ids(prototype_ids=["gear.offense"], index=_INDEX)


def test_resolve_slot_selector_matches_open_slot() -> None:
    """--slot 按开放槽选原型（抗原型库变更，比记 id 好）。"""
    resolved = resolve_prototype_ids(slot="on_autonomous_affixes", index=_INDEX)

    assert resolved == ["proto.summon"]


def test_resolve_explicit_then_slot_without_duplicates() -> None:
    """显式 id 在前，选择器命中项按索引顺序追加且去重。"""
    resolved = resolve_prototype_ids(
        prototype_ids=["proto.summon"],
        slot="on_autonomous_affixes",
        index=_INDEX,
    )

    assert resolved == ["proto.summon"]


def test_resolve_keyword_matches_multiple_fields() -> None:
    assert resolve_prototype_ids(keyword="爆发", index=_INDEX) == ["proto.burst"]
    assert resolve_prototype_ids(keyword="autonomous", index=_INDEX) == ["proto.summon"]

    with pytest.raises(ValueError, match="没有匹配的原型"):
        resolve_prototype_ids(keyword="不存在的词", index=_INDEX)


def test_filter_entries_keeps_index_order() -> None:
    matched = filter_entries(_INDEX, keyword="damage")

    assert [entry["prototype_id"] for entry in matched] == ["proto.attack"]


#######################################################################################################################################
def test_spoils_strict_requires_exact_count() -> None:
    """默认严格：指定不足候选数直接报错，提示加 --fill-random。"""
    with pytest.raises(ValueError, match="--fill-random"):
        resolve_candidate_ids(count=3, prototype_ids=["proto.summon"], index=_INDEX)


def test_spoils_rejects_more_than_count() -> None:
    with pytest.raises(ValueError, match="候选最多 3 张"):
        resolve_candidate_ids(
            count=3,
            prototype_ids=[
                "proto.summon",
                "proto.burst",
                "proto.attack",
                "proto.summon",
            ],
            index=_INDEX,
        )


def test_spoils_fill_random_keeps_explicit_prefix_and_is_seeded() -> None:
    """--fill-random：显式 id 保留在前，剩余按 seed 确定性补足，且不重复已选项。"""
    first = resolve_candidate_ids(
        count=3,
        prototype_ids=["proto.summon"],
        fill_random=True,
        seed=7,
        index=_INDEX,
    )
    second = resolve_candidate_ids(
        count=3,
        prototype_ids=["proto.summon"],
        fill_random=True,
        seed=7,
        index=_INDEX,
    )

    assert first == second
    assert first[0] == "proto.summon"
    assert len(first) == 3
    assert len(set(first)) == 3


def test_spoils_fill_random_reports_insufficient_pool() -> None:
    with pytest.raises(ValueError, match="原型库不足以补足候选"):
        resolve_candidate_ids(
            count=4,
            prototype_ids=["proto.summon"],
            fill_random=True,
            index=_INDEX,
        )


#######################################################################################################################################
def test_resolve_candidate_ids_without_target_takes_what_is_given() -> None:
    """不给目标张数时「给几个就是几个」：游戏常量不构成约束。"""
    assert resolve_candidate_ids(prototype_ids=["proto.summon"], index=_INDEX) == [
        "proto.summon"
    ]
    assert resolve_candidate_ids(slot="on_autonomous_affixes", index=_INDEX) == [
        "proto.summon"
    ]


def test_resolve_candidate_ids_fill_requires_target() -> None:
    with pytest.raises(ValueError, match="需要先给出目标张数"):
        resolve_candidate_ids(
            prototype_ids=["proto.summon"], fill_random=True, index=_INDEX
        )
