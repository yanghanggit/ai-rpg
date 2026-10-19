"""运转词缀（`engine_affixes`）的模型层约定。

类别由槽位本身决定（不靠词缀名标记），且只能挂在可出牌的牌上；
该槽暂不进入生成契约。
"""

import pytest

from ai_rpg.models import (
    AFFIX_FIELDS,
    DESIGNABLE_AFFIX_FIELDS,
    Card,
    TargetType,
    validate_affix_slot,
)


def _make_card(*, playable: bool = True) -> Card:
    return Card(
        name="怒火",
        description="",
        cost=1,
        damage=2,
        hit_count=1,
        target_type=TargetType.SINGLE,
        playable=playable,
    )


def test_engine_slot_is_an_affix_field_but_not_designable() -> None:
    """运转型槽存在，但暂不开放给生成侧（agent 设计）。"""
    assert "engine_affixes" in AFFIX_FIELDS
    assert "engine_affixes" not in DESIGNABLE_AFFIX_FIELDS


def test_affix_name_is_freeform() -> None:
    """词缀名照常写风味名：类别由槽位决定，不靠名字里的关键字标记。"""
    card = _make_card()
    ok = validate_affix_slot("engine_affixes", "[余刃]:打出后复制一张自己", card)
    assert ok.ok


def test_engine_affix_on_unplayable_card_is_rejected() -> None:
    """不可出牌的牌不会进入结算，带运转型词缀属无效组合。"""
    card = _make_card(playable=False)
    result = validate_affix_slot(
        "engine_affixes", "[engine_增殖]:打出后复制一张自己", card
    )
    assert not result.ok
    assert "playable" in result.reason


def test_engine_affix_still_requires_standard_format() -> None:
    """与其他槽一样必须是 `[名字]:机械结算描述`。"""
    card = _make_card()
    assert not validate_affix_slot("engine_affixes", "engine_增殖", card).ok


@pytest.mark.parametrize("name", ["engine_增殖", "ENGINE_COPY", "EngineBurn"])
def test_keyword_match_is_case_insensitive(name: str) -> None:
    card = _make_card()
    assert validate_affix_slot(
        "engine_affixes", f"[{name}]:打出后复制一张自己", card
    ).ok
