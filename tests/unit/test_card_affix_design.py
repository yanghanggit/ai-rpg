"""卡牌词缀设计校验（`validate_affix_slot`）与「非法置空」（`apply_affix_design`）的单元测试。"""

from ai_rpg.models import (
    Card,
    apply_affix_design,
    validate_affix_slot,
)


def _card(**overrides: object) -> Card:
    base: dict[str, object] = {
        "name": "原型",
        "description": "原型描述",
        "on_play_affixes": ["[诅咒]:打出时对目标施加减益"],
        "damage": 2,
    }
    base.update(overrides)
    return Card.model_validate(base)


# ── validate_affix_slot ────────────────────────────────────────────────


def test_valid_field_anchored_affix_passes() -> None:
    card = _card()
    result = validate_affix_slot(
        "on_play_affixes", "[断筋]:打出时对目标造成本卡 damage×3 的伤害", card
    )
    assert result.ok


def test_damage_without_damage_field_is_allowed() -> None:
    # 字段锚点是「书写约定」而非硬拦截：可结算性交给结算原语契约与 agent 自检。
    result = validate_affix_slot(
        "on_play_affixes", "[断筋]:打出时对目标造成伤害", _card()
    )
    assert result.ok


def test_block_without_block_field_is_allowed() -> None:
    result = validate_affix_slot("on_play_affixes", "[铁壁]:打出时获得格挡", _card())
    assert result.ok


def test_transferable_holder_allowed_without_source() -> None:
    card = _card(transferable=True)
    holder = validate_affix_slot(
        "on_play_affixes", "[推手]:打出时对持有者叠加标记", card
    )
    non_source = validate_affix_slot(
        "on_play_affixes", "[推手]:打出时对非 source 者叠加标记", card
    )
    assert holder.ok
    assert non_source.ok


def test_non_transferable_holder_needs_no_source() -> None:
    card = _card(transferable=False)
    result = validate_affix_slot(
        "on_play_affixes", "[自守]:打出时对目标持有者叠加标记", card
    )
    assert result.ok


def test_independent_number_allowed() -> None:
    # 数值不加护栏：独立数字不再拦截（可结算性交给契约与 agent 自检）。
    result = validate_affix_slot(
        "on_play_affixes",
        "[断筋]:打出时对目标造成本卡 damage 的伤害，持续 3 回合",
        _card(),
    )
    assert result.ok


def test_condition_number_allowed() -> None:
    # 「BLOCK 为 0」这类条件数字不再误杀（此前的假阳性）。
    result = validate_affix_slot(
        "on_play_affixes",
        "[淬口啍铁]:若目标的 BLOCK 为 0，本卡本次 damage×2",
        _card(),
    )
    assert result.ok


def test_multiplier_forms_are_accepted() -> None:
    card = _card()
    for text in (
        "[断筋]:打出时对目标造成本卡 damage×2 的伤害",
        "[断筋]:打出时对目标造成本卡 damagex2 的伤害",
        "[断筋]:打出时对目标造成本卡 damage*2 的伤害",
        "[断筋]:打出时对目标造成本卡 damage x 2 的伤害",
    ):
        assert validate_affix_slot("on_play_affixes", text, card).ok, text


def test_placeholder_fails() -> None:
    result = validate_affix_slot(
        "on_play_affixes", "[词缀名]:本次出牌产生何种效果", _card()
    )
    assert not result.ok


def test_missing_brackets_fails() -> None:
    # 硬格式：方括号必需（客户端按 `[名称]:说明` 解析）。
    result = validate_affix_slot(
        "on_play_affixes", "断筋:打出时对目标造成本卡 damage×2 的伤害", _card()
    )
    assert not result.ok
    assert "方括号" in result.reason


def test_on_play_rejected_for_unplayable_card() -> None:
    result = validate_affix_slot(
        "on_play_affixes", "[诅咒]:打出时对目标施加减益", _card(playable=False)
    )
    assert not result.ok


def test_autonomous_affix_valid() -> None:
    result = validate_affix_slot(
        "on_autonomous_affixes",
        "[自主]:持有者每次 pass turn 时对一名随机敌人造成本卡 damage 的伤害",
        _card(),
    )
    assert result.ok


def test_autonomous_affix_allowed_on_unplayable_card() -> None:
    # 自主运行牌通常是纯状态（playable=False），不应被即时词缀的 playable 约束误伤。
    result = validate_affix_slot(
        "on_autonomous_affixes",
        "[自主]:持有者每次 pass turn 时对一名敌人造成本卡 damage 的伤害",
        _card(playable=False, retain=True),
    )
    assert result.ok


def test_autonomous_affix_rejected_for_ethereal_card() -> None:
    # 虚无牌会在自主运行阶段之前被消耗，自主词缀永不触发：硬拦截。
    result = validate_affix_slot(
        "on_autonomous_affixes",
        "[自主]:持有者每次 pass turn 时对一名敌人造成本卡 damage 的伤害",
        _card(ethereal=True),
    )
    assert not result.ok
    assert "虚无" in result.reason


def test_apply_autonomous_affix() -> None:
    card = _card(
        on_play_affixes=[],
        on_autonomous_affixes=["[词缀名]:占位"],
        retain=True,
    )
    submitted = {"on_autonomous_affixes": ["[自主]:对一名敌人造成本卡 damage 的伤害"]}

    applied, notes = apply_affix_design("角色.无名", card, submitted)

    assert applied == 1
    assert notes == []
    assert card.on_autonomous_affixes == ["[自主]:对一名敌人造成本卡 damage 的伤害"]


# ── apply_affix_design ─────────────────────────────────────────────────


def test_valid_design_is_applied() -> None:
    card = _card()
    submitted = {"on_play_affixes": ["[断筋]:打出时对目标造成本卡 damage×2 的伤害"]}

    applied, fallbacks = apply_affix_design("角色.无名", card, submitted)

    assert applied == 1
    assert fallbacks == []
    assert card.on_play_affixes == ["[断筋]:打出时对目标造成本卡 damage×2 的伤害"]


def test_invalid_design_empties_slot() -> None:
    card = _card()
    # 格式非法（缺方括号）：整槽置空。
    submitted = {"on_play_affixes": ["断筋:打出时对目标造成本卡 damage×2 的伤害"]}

    applied, notes = apply_affix_design("角色.无名", card, submitted)

    assert applied == 0
    assert len(notes) == 1
    assert card.on_play_affixes == []


def test_empty_design_empties_slot() -> None:
    card = _card()
    applied, notes = apply_affix_design("角色.无名", card, {"on_play_affixes": []})

    assert applied == 0
    assert len(notes) == 1
    assert card.on_play_affixes == []


def test_design_for_empty_slot_is_ignored() -> None:
    card = _card(on_play_affixes=[], on_hit_affixes=[])
    applied, notes = apply_affix_design(
        "角色.无名", card, {"on_hit_affixes": ["[逆鳞]:被命中时反击"]}
    )

    assert applied == 0
    assert len(notes) == 1
    assert card.on_hit_affixes == []


def test_omitted_slot_empties_slot() -> None:
    # 原型词缀是「引导」而非回退答案：不提交即置空。
    card = _card()
    applied, notes = apply_affix_design("角色.无名", card, {})

    assert applied == 0
    assert len(notes) == 1
    assert card.on_play_affixes == []
