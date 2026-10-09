"""LLM 多值文本字段（``List[str]``）的统一语义测试。

全局约定：这类字段一律多值——每个元素是一条完整、独立的字符串。
本文件覆盖：
- 清洗（``normalize_str_list``）与保边界渲染（``render_*``）；
- 模型层 ``NormalizedStrList`` 注解自动清洗；
- 词缀「逐条校验 + 整槽回退」支持多条；
- 各消费端（出牌/回合结束/怪物决策/消耗品仲裁）逐条渲染全部条目；
- 消耗品堆叠身份纳入全部效果提示。
"""

from ai_rpg.models import (
    Artifact,
    Card,
    ConsumableItem,
    apply_affix_design,
    normalize_str_list,
    render_labeled_str_list,
    render_str_list,
)
from ai_rpg.models.utils import append_item_with_stacking
from ai_rpg.systems.monster_pre_play_system import _format_card
from ai_rpg.systems.play_cards_arbitration_system import _build_card_data_lines
from ai_rpg.systems.turn_end_arbitration_system import _build_turn_end_card_lines
from ai_rpg.systems.use_consumable_item_arbitration_system import (
    _build_consumable_arbitration_prompt,
)

AFFIX_A = "[穿甲]:本卡 damage 结算时无视目标 block"
AFFIX_B = "[自损]:打出时对自身结算本卡 damage×1 的伤害"


# ---------------------------------------------------------------------------
# 清洗 / 渲染工具
# ---------------------------------------------------------------------------


def test_normalize_strips_drops_empty_and_dedupes() -> None:
    assert normalize_str_list([" a ", "", "  ", "a", "b "]) == ["a", "b"]


def test_render_str_list_keeps_item_boundaries() -> None:
    assert render_str_list(["a", "b"]) == "- a\n- b"
    assert render_str_list([]) == "无"
    assert render_str_list(["a"], indent="  ") == "  - a"


def test_render_labeled_str_list_formats_block() -> None:
    assert render_labeled_str_list("- 词缀", []) == "- 词缀：无"
    assert (
        render_labeled_str_list("- 词缀", ["a", "b"], indent="  ")
        == "- 词缀：\n  - a\n  - b"
    )


# ---------------------------------------------------------------------------
# 模型层 NormalizedStrList 注解
# ---------------------------------------------------------------------------


def test_card_affix_fields_are_normalized() -> None:
    card = Card(
        name="x",
        description="",
        on_play_affixes=[" " + AFFIX_A + " ", "", AFFIX_A, AFFIX_B],
    )
    assert card.on_play_affixes == [AFFIX_A, AFFIX_B]


def test_consumable_prompt_is_normalized() -> None:
    item = ConsumableItem(name="消耗品.x", description="", on_use_prompt=[" a ", ""])
    assert item.on_use_prompt == ["a"]


def test_artifact_modifiers_are_normalized() -> None:
    artifact = Artifact(name="神器.x", system_message="", modifiers=[" r ", ""])
    assert artifact.modifiers == ["r"]


# ---------------------------------------------------------------------------
# apply_affix_design：多值逐条校验 + 整槽回退
# ---------------------------------------------------------------------------


def _card(**overrides: object) -> Card:
    base: dict[str, object] = {
        "name": "原型",
        "description": "原型描述",
        "on_play_affixes": [AFFIX_B],
        "damage": 2,
    }
    base.update(overrides)
    return Card.model_validate(base)


def test_apply_multiple_affixes() -> None:
    card = _card()
    applied, fallbacks = apply_affix_design(
        "角色.无名", card, {"on_play_affixes": [AFFIX_A, AFFIX_B]}
    )
    assert applied == 2
    assert fallbacks == []
    assert card.on_play_affixes == [AFFIX_A, AFFIX_B]


def test_apply_dedupes_and_drops_blank_affixes() -> None:
    card = _card()
    applied, fallbacks = apply_affix_design(
        "角色.无名", card, {"on_play_affixes": [" " + AFFIX_A + " ", "", AFFIX_A]}
    )
    assert applied == 1
    assert fallbacks == []
    assert card.on_play_affixes == [AFFIX_A]


def test_one_invalid_affix_falls_back_whole_slot() -> None:
    card = _card()
    applied, fallbacks = apply_affix_design(
        "角色.无名", card, {"on_play_affixes": [AFFIX_A, "[断裂]:打出时造成伤害"]}
    )
    assert applied == 0
    assert len(fallbacks) == 1
    assert card.on_play_affixes == [AFFIX_B]


# ---------------------------------------------------------------------------
# 消费端逐条渲染
# ---------------------------------------------------------------------------


def test_play_card_lines_render_all_affixes_separately() -> None:
    text = _build_card_data_lines(_card(on_play_affixes=[AFFIX_A, AFFIX_B]))
    assert AFFIX_A in text and AFFIX_B in text
    assert f"{AFFIX_A}、{AFFIX_B}" not in text


def test_turn_end_lines_render_all_affixes_separately() -> None:
    text = _build_turn_end_card_lines(_card(on_turn_end_affixes=[AFFIX_A, AFFIX_B]))
    assert AFFIX_A in text and AFFIX_B in text
    assert f"{AFFIX_A}、{AFFIX_B}" not in text


def test_monster_decision_lines_render_all_affixes_separately() -> None:
    text = _format_card(_card(on_play_affixes=[AFFIX_A, AFFIX_B]))
    assert AFFIX_A in text and AFFIX_B in text
    assert f"{AFFIX_A}、{AFFIX_B}" not in text


def test_consumable_prompt_renders_all_effect_prompts() -> None:
    item = ConsumableItem(
        name="消耗品.x",
        description="描述",
        on_use_prompt=["对目标造成 3 点伤害。", "使目标恢复 2 点 HP。"],
    )
    text = _build_consumable_arbitration_prompt("角色.测试", item, [], 1, [])
    assert "对目标造成 3 点伤害。" in text
    assert "使目标恢复 2 点 HP。" in text
    assert "逐条全部结算" in text


# ---------------------------------------------------------------------------
# 消耗品堆叠身份纳入全部效果提示
# ---------------------------------------------------------------------------


def _consumable(prompts: list[str]) -> ConsumableItem:
    return ConsumableItem(name="消耗品.x", description="描述", on_use_prompt=prompts)


def test_same_multi_prompts_stack() -> None:
    prompts = ["对目标造成 3 点伤害。", "使目标恢复 2 点 HP。"]
    result = append_item_with_stacking([_consumable(prompts)], _consumable(prompts))
    assert len(result) == 1
    assert result[0].count == 2


def test_different_extra_prompt_does_not_stack() -> None:
    result = append_item_with_stacking(
        [_consumable(["对目标造成 3 点伤害。", "使目标恢复 2 点 HP。"])],
        _consumable(["对目标造成 3 点伤害。"]),
    )
    assert len(result) == 2
