"""card_design 引擎的候选格式化、prompt 组装与提交暂存的单元测试。"""

from ai_rpg.models import Card
from ai_rpg.systems.card_design import (
    Candidate,
    CardDesign,
    _handle_submit_card,
    format_candidate,
)


def _candidate() -> Candidate:
    card = Card(
        name="骨架卡",
        description="",
        damage=2,
        block=1,
        retain=True,
        on_turn_end_affixes=[
            "[中毒]:回合结束时对非 source 者结算本卡 damage×1 的持续伤害"
        ],
    )
    return Candidate(
        card=card,
        archetype="攻击端",
        archetype_subtype="成长性伤害",
        summary="摘要",
        design="指导",
    )


def test_format_card_uses_index_and_slots_without_duplication() -> None:
    text = format_candidate(_candidate(), 1)

    assert "- #1" in text
    assert "uuid" not in text
    assert "攻击端 / 成长性伤害" in text
    assert "摘要" in text
    assert "设计: 指导" in text
    assert "可设计槽: on_turn_end_affixes" in text
    # 骨架数值 / 只读特性已并入 design，不在 formatter 里重复打印
    assert "骨架（数值可微调）" not in text
    assert "特性（只读）" not in text
    # 原型占位词缀不再单列（变量池与方向已在 design 里）
    assert "[中毒]" not in text


def _submit_card() -> Card:
    """带两个可设计槽（非空=有引导）的骨架卡，供提交校验用。"""
    return Card(
        name="骨架卡",
        description="",
        damage=2,
        on_play_affixes=["[引导]:打出时取一个内建数值对目标造成伤害"],
        on_turn_end_affixes=[
            "[引导]:回合结束时对非 source 者结算本卡 damage×1 的持续伤害"
        ],
    )


def test_handle_submit_stores_all_design_fields() -> None:
    card = _submit_card()
    edits: list[CardDesign] = []
    msg = _handle_submit_card(
        edits,
        [card],
        card_index=1,
        name="朱批",
        description="落款",
        cost=2,
        damage=3,
        on_play_affixes=["[朱批]:打出时对目标造成本卡 damage×1 的伤害"],
        on_hit_affixes=None,
        on_turn_end_affixes=[
            "[余墨]:回合结束时对非 source 者结算本卡 damage×1 的持续伤害"
        ],
    )

    assert "已记录" in msg
    assert len(edits) == 1
    edit = edits[0]
    assert edit.uuid == card.uuid
    assert edit.name == "朱批"
    assert (edit.cost, edit.damage) == (2, 3)
    assert edit.on_play_affixes == ["[朱批]:打出时对目标造成本卡 damage×1 的伤害"]
    assert edit.on_hit_affixes is None


def test_handle_submit_rejects_invalid_affix() -> None:
    # 缺方括号：handler 应返回错误且不记录，让 agent 修正重提。
    card = _submit_card()
    edits: list[CardDesign] = []
    msg = _handle_submit_card(
        edits,
        [card],
        card_index=1,
        name="朱批",
        description="落款",
        on_play_affixes=["朱批:打出时对目标造成本卡 damage×1 的伤害"],
    )

    assert "错误" in msg
    assert edits == []


def test_handle_submit_rejects_bad_card_index() -> None:
    card = _submit_card()
    edits: list[CardDesign] = []
    msg = _handle_submit_card(
        edits, [card], card_index=3, name="朱批", description="落款"
    )

    assert "超出范围" in msg
    assert edits == []
