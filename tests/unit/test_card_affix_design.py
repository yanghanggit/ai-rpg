"""卡牌词缀设计校验（`validate_affix_slot`）与「整槽回退」（`apply_affix_design`）的单元测试。"""

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


def test_damage_without_damage_field_fails() -> None:
    result = validate_affix_slot(
        "on_play_affixes", "[断筋]:打出时对目标造成伤害", _card()
    )
    assert not result.ok
    assert "damage" in result.reason


def test_block_without_block_field_fails() -> None:
    result = validate_affix_slot("on_play_affixes", "[铁壁]:打出时获得格挡", _card())
    assert not result.ok
    assert "block" in result.reason


def test_transferable_holder_requires_source() -> None:
    card = _card(transferable=True)
    bad = validate_affix_slot("on_play_affixes", "[推手]:打出时对持有者叠加标记", card)
    good = validate_affix_slot(
        "on_play_affixes", "[推手]:打出时对非 source 者叠加标记", card
    )
    assert not bad.ok
    assert good.ok


def test_non_transferable_holder_needs_no_source() -> None:
    card = _card(transferable=False)
    result = validate_affix_slot(
        "on_play_affixes", "[自守]:打出时对目标持有者叠加标记", card
    )
    assert result.ok


def test_independent_number_fails() -> None:
    card = _card()
    result = validate_affix_slot(
        "on_play_affixes",
        "[断筋]:打出时对目标造成本卡 damage 的伤害，持续 3 回合",
        card,
    )
    assert not result.ok
    assert "独立数值" in result.reason


def test_multiplier_forms_are_accepted() -> None:
    card = _card()
    for text in (
        "[断筋]:打出时对目标造成本卡 damage×2 的伤害",
        "[断筋]:打出时对目标造成本卡 damagex2 的伤害",
        "[断筋]:打出时对目标造成本卡 damage*2 的伤害",
        "[断筋]:打出时对目标造成本卡 damage x 2 的伤害",
    ):
        assert validate_affix_slot("on_play_affixes", text, card).ok, text


def test_hit_count_multiplier_bound_by_timing() -> None:
    card = _card()
    ok = validate_affix_slot(
        "on_play_affixes", "[乱影]:打出时额外结算本卡 hit_count×2 次", card
    )
    over = validate_affix_slot(
        "on_play_affixes", "[乱影]:打出时额外结算本卡 hit_count×3 次", card
    )
    assert ok.ok
    assert not over.ok


def test_damage_multiplier_bound_by_timing() -> None:
    card = _card(
        on_turn_end_affixes=[
            "[中毒]:回合结束时对非 source 者结算本卡 damage×1 的持续伤害"
        ]
    )
    ok = validate_affix_slot(
        "on_turn_end_affixes",
        "[中毒]:回合结束时对非 source 者结算本卡 damage×2 的持续伤害",
        card,
    )
    over = validate_affix_slot(
        "on_turn_end_affixes",
        "[中毒]:回合结束时对非 source 者结算本卡 damage×3 的持续伤害",
        card,
    )
    assert ok.ok
    assert not over.ok


def test_placeholder_fails() -> None:
    result = validate_affix_slot(
        "on_play_affixes", "[词缀名]:本次出牌产生何种效果", _card()
    )
    assert not result.ok


def test_on_play_rejected_for_unplayable_card() -> None:
    result = validate_affix_slot(
        "on_play_affixes", "[诅咒]:打出时对目标施加减益", _card(playable=False)
    )
    assert not result.ok


# ── apply_affix_design ─────────────────────────────────────────────────


def test_valid_design_is_applied() -> None:
    card = _card()
    submitted = {"on_play_affixes": ["[断筋]:打出时对目标造成本卡 damage×2 的伤害"]}

    applied, fallbacks = apply_affix_design("角色.无名", card, submitted)

    assert applied == 1
    assert fallbacks == []
    assert card.on_play_affixes == ["[断筋]:打出时对目标造成本卡 damage×2 的伤害"]


def test_invalid_design_falls_back_whole_slot() -> None:
    card = _card()
    submitted = {"on_play_affixes": ["[断筋]:打出时对目标造成伤害"]}

    applied, fallbacks = apply_affix_design("角色.无名", card, submitted)

    assert applied == 0
    assert len(fallbacks) == 1
    assert card.on_play_affixes == ["[诅咒]:打出时对目标施加减益"]


def test_empty_design_falls_back_to_prototype() -> None:
    card = _card()
    applied, fallbacks = apply_affix_design("角色.无名", card, {"on_play_affixes": []})

    assert applied == 0
    assert len(fallbacks) == 1
    assert card.on_play_affixes == ["[诅咒]:打出时对目标施加减益"]


def test_design_for_empty_slot_is_ignored() -> None:
    card = _card(on_hit_affixes=[])
    applied, fallbacks = apply_affix_design(
        "角色.无名", card, {"on_hit_affixes": ["[逆鳞]:被命中时反击"]}
    )

    assert applied == 0
    assert len(fallbacks) == 1
    assert card.on_hit_affixes == []


def test_omitted_slot_keeps_prototype() -> None:
    card = _card()
    applied, fallbacks = apply_affix_design("角色.无名", card, {})

    assert applied == 0
    assert fallbacks == []
    assert card.on_play_affixes == ["[诅咒]:打出时对目标施加减益"]
