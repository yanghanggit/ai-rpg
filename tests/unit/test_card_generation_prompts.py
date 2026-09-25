"""四类「创造卡牌」任务的提示词组装矩阵测试。

确保：字段语义（它是什么）与词缀设计规范（如何设计）在使用点按需组装，
且词缀槽位约束只出现在真正继承原型的任务里（spoils / 初始牌库），
工坊从零设计时不出现，牌库叙事润色（词缀只读）不得出现设计规范。
"""

from types import SimpleNamespace
from typing import Any

from ai_rpg.models import Card, MaterialItem
from ai_rpg.systems.assemble_deck_system import _build_deck_prompt
from ai_rpg.systems.craft_gear_item_action_system import _build_craft_gear_prompt
from ai_rpg.systems.generate_spoils_action_system import (
    _build_spoils_prompt,
    _Candidate,
)
from ai_rpg.systems.initialize_deck_action_system import _build_deck_init_prompt

FIELD_SPEC = "## 卡牌字段语义"
AFFIX_SPEC = "## 词缀设计规范"
SLOT_RULE = "只能对"

_ENTITY: Any = SimpleNamespace(name="角色.测试")


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


def _candidate() -> _Candidate:
    return _Candidate(
        card=_card(),
        archetype="攻击端",
        archetype_subtype="成长性伤害",
        summary="摘要",
        guide="指导",
    )


def test_init_prompt_has_field_spec_but_no_affix_design() -> None:
    text = _build_deck_init_prompt(_ENTITY, [_card()])

    assert FIELD_SPEC in text
    assert AFFIX_SPEC not in text
    assert SLOT_RULE not in text


def test_assemble_prompt_has_both_specs_and_slot_rule() -> None:
    text = _build_deck_prompt("角色.测试")

    assert FIELD_SPEC in text
    assert AFFIX_SPEC in text
    assert SLOT_RULE in text


def test_spoils_prompt_has_both_specs_and_slot_rule() -> None:
    text = _build_spoils_prompt(_ENTITY, [_candidate()])

    assert FIELD_SPEC in text
    assert AFFIX_SPEC in text
    assert SLOT_RULE in text


def test_craft_prompt_has_both_specs_without_slot_rule() -> None:
    material = MaterialItem(name="材料.测试", description="一块材料", count=1)
    text = _build_craft_gear_prompt([material])

    assert FIELD_SPEC in text
    assert AFFIX_SPEC in text
    assert SLOT_RULE not in text


def test_no_prompt_keeps_obsolete_slot_wording() -> None:
    material = MaterialItem(name="材料.测试", description="一块材料", count=1)
    texts = [
        _build_deck_init_prompt(_ENTITY, [_card()]),
        _build_deck_prompt("角色.测试"),
        _build_spoils_prompt(_ENTITY, [_candidate()]),
        _build_craft_gear_prompt([material]),
    ]
    for text in texts:
        assert "只能在原型已存在的槽位内设计" not in text
