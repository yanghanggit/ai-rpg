"""各「创造卡牌」任务的提示词组装矩阵测试。

字段语义（它是什么）与词缀规范（如何设计）按使用点组装；四条路径均已不再
注入全局规范，改为「原型 design + submit_card 工具契约」。
"""

from ai_rpg.models import Card, MaterialItem
from ai_rpg.systems.assemble_dungeon_deck_system import (
    DECK_SIZE,
    _build_deck_select_prompt,
)
from ai_rpg.systems.card_design import (
    Candidate,
    build_card_design_prompt,
)
from ai_rpg.systems.context_compaction_prompt_builders import build_compaction_prompt
from ai_rpg.systems.craft_consumable_item_action_system import (
    _build_consumable_select_prompt,
)
from ai_rpg.systems.craft_gear_item_action_system import _build_gear_select_prompt

FIELD_SPEC = "## 卡牌字段语义"
AFFIX_SPEC = "## 词缀设计规范"
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


def test_deck_select_prompt_has_no_global_specs() -> None:
    # 选型阶段只负责挑原型；字段语义与词缀规范改由每张原型的 design
    # + submit_card 的工具 schema 下发，提示词不再注入两个全局规范。
    text = _build_deck_select_prompt()

    assert FIELD_SPEC not in text
    assert AFFIX_SPEC not in text
    assert "select_cards" in text
    assert str(DECK_SIZE) in text


def test_card_design_prompt_is_design_driven_without_global_rules() -> None:
    text = build_card_design_prompt([_candidate()])

    # spoils 不再注入两个全局规范，也不再有内联词缀规则块；
    # 词缀硬边界随 submit_card 的工具 schema 下发，提示词只保留任务 + 叙事。
    assert FIELD_SPEC not in text
    assert AFFIX_SPEC not in text
    assert "## 词缀规则" not in text
    assert "设计: 指导" in text
    assert SPOILS_SLOT in text


def test_consumable_select_prompt_has_no_global_specs() -> None:
    # 消耗品工坊已迁移到 card_design：选型阶段不注入全局规范。
    material = MaterialItem(name="材料.测试", description="一块材料", count=1)
    text = _build_consumable_select_prompt([material])

    assert FIELD_SPEC not in text
    assert AFFIX_SPEC not in text
    assert "select_cards" in text
    assert "材料.测试" in text


def test_gear_select_prompt_has_no_global_specs() -> None:
    # 装备工坊已迁移到 card_design：选型阶段不注入全局规范。
    material = MaterialItem(name="材料.测试", description="一块材料", count=1)
    text = _build_gear_select_prompt([material])

    assert FIELD_SPEC not in text
    assert AFFIX_SPEC not in text
    assert "select_cards" in text
    assert "材料.测试" in text


def test_no_prompt_keeps_obsolete_slot_wording() -> None:
    material = MaterialItem(name="材料.测试", description="一块材料", count=1)
    texts = [
        _build_deck_select_prompt(),
        build_card_design_prompt([_candidate()]),
        _build_gear_select_prompt([material]),
    ]
    for text in texts:
        assert "只能在原型已存在的槽位内设计" not in text


def test_task_prompts_do_not_restate_entity_identity() -> None:
    # 身份由 entity_factory 编译的 SystemMessage 承载（「# 名称」+「你扮演角色/场景/世界」），
    # 任务提示词不再重复声明「你是 X」；这些提示词的 messages 都带着该 SystemMessage。
    for text in (
        _build_deck_select_prompt(),
        build_compaction_prompt(),
    ):
        assert "你是" not in text
        assert "你扮演" not in text
