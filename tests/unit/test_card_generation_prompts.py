"""三类「创造卡牌」任务的提示词组装矩阵测试。

字段语义（它是什么）与词缀规范（如何设计）按使用点组装：
- spoils：不再注入全局规范，改为「原型 design + submit_card 工具契约」；
- 其余任务（初始牌库 / 工坊）目前仍注入两个全局规范。
"""

from ai_rpg.models import Card, MaterialItem
from ai_rpg.systems.assemble_dungeon_deck_system import _build_deck_prompt
from ai_rpg.systems.card_design import (
    Candidate,
    build_card_design_prompt,
)
from ai_rpg.systems.craft_gear_item_action_system import _build_craft_gear_prompt

FIELD_SPEC = "## 卡牌字段语义"
AFFIX_SPEC = "## 词缀设计规范"
SLOT_RULE = "只能对"
SPOILS_SLOT = "可设计槽"


def _card() -> Card:
    return Card(
        name="骨架卡",
        description="",
        damage=2,
        block=1,
        on_turn_end_affixes=[
            "[中毒]:回合结束时对非 source 者结算本卡 damage×1 的持续伤害"
        ],
    )


def _candidate() -> Candidate:
    return Candidate(
        card=_card(),
        archetype="攻击端",
        archetype_subtype="成长性伤害",
        summary="摘要",
        design="指导",
    )


def test_assemble_prompt_has_both_specs_and_slot_rule() -> None:
    text = _build_deck_prompt("角色.测试")

    assert FIELD_SPEC in text
    assert AFFIX_SPEC in text
    assert SLOT_RULE in text


def test_card_design_prompt_is_design_driven_without_global_rules() -> None:
    text = build_card_design_prompt([_candidate()])

    # spoils 不再注入两个全局规范，也不再有内联词缀规则块；
    # 词缀硬边界随 submit_card 的工具 schema 下发，提示词只保留任务 + 叙事。
    assert FIELD_SPEC not in text
    assert AFFIX_SPEC not in text
    assert "## 词缀规则" not in text
    assert "设计: 指导" in text
    assert SPOILS_SLOT in text


def test_craft_prompt_has_both_specs_without_slot_rule() -> None:
    material = MaterialItem(name="材料.测试", description="一块材料", count=1)
    text = _build_craft_gear_prompt([material])

    assert FIELD_SPEC in text
    assert AFFIX_SPEC in text
    assert SLOT_RULE not in text


def test_no_prompt_keeps_obsolete_slot_wording() -> None:
    material = MaterialItem(name="材料.测试", description="一块材料", count=1)
    texts = [
        _build_deck_prompt("角色.测试"),
        build_card_design_prompt([_candidate()]),
        _build_craft_gear_prompt([material]),
    ]
    for text in texts:
        assert "只能在原型已存在的槽位内设计" not in text
