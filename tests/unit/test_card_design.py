"""card_design 引擎的候选格式化、prompt 组装、选型与提交暂存的单元测试。"""

import pytest

from ai_rpg.models import Card
from ai_rpg.systems.card_design import (
    Candidate,
    CardDesign,
    _CardSelection,
    _handle_finish_cards,
    _handle_select_cards,
    _handle_submit_card,
    build_select_cards_tool,
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


def test_build_select_cards_tool_uses_size() -> None:
    tool = build_select_cards_tool(3)

    assert tool.function.name == "select_cards"
    props = tool.function.parameters["properties"]["prototype_ids"]
    assert props["minItems"] == 3
    assert props["maxItems"] == 3


def test_select_cards_stores_ids_and_allows_duplicates() -> None:
    valid = {"proto.attack", "proto.block", "proto.burst", "proto.heal", "proto.weaken"}
    selection = _CardSelection()
    ids = ["proto.attack", "proto.attack", "proto.burst", "proto.heal", "proto.block"]

    result = _handle_select_cards(selection, valid, 5, ids)

    assert "已记录" in result
    assert selection.prototype_ids == ids


def test_select_cards_rejects_wrong_count() -> None:
    selection = _CardSelection()

    result = _handle_select_cards(selection, {"proto.attack"}, 5, ["proto.attack"])

    assert result.startswith("错误")
    assert selection.prototype_ids == []


def test_select_cards_rejects_unknown_id() -> None:
    valid = {"proto.attack", "proto.block", "proto.burst", "proto.heal", "proto.weaken"}
    selection = _CardSelection()
    ids = ["proto.attack", "proto.attack", "proto.burst", "proto.heal", "proto.不存在"]

    result = _handle_select_cards(selection, valid, 5, ids)

    assert result.startswith("错误")
    assert selection.prototype_ids == []


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


def test_handle_submit_rejects_multiple_affixes_in_one_slot() -> None:
    # 每个词缀槽至多一条（schema maxItems=1 之外的兜底）。
    card = _submit_card()
    edits: list[CardDesign] = []
    msg = _handle_submit_card(
        edits,
        [card],
        card_index=1,
        name="朱批",
        description="落款",
        on_turn_end_affixes=[
            "[余墨]:回合结束时对非 source 者结算本卡 damage×1 的持续伤害",
            "[叠墨]:回合结束时对非 source 者结算本卡 damage×1 的持续伤害",
        ],
    )

    assert "至多一条" in msg
    assert edits == []


def test_finish_cards_requires_every_candidate_designed() -> None:
    """未全部提交（或被拒）时，finish_cards 不能静默结束，必须报错让模型补交。"""
    first = _candidate().card
    second = _candidate().card
    designed = [CardDesign(uuid=first.uuid, name="甲", description="一")]

    with pytest.raises(ValueError, match="#2"):
        _handle_finish_cards(designed, [first, second])

    designed.append(CardDesign(uuid=second.uuid, name="乙", description="二"))
    assert _handle_finish_cards(designed, [first, second]) == "已结束本次设计。"
