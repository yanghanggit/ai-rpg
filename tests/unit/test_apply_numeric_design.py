"""apply_numeric_design 的单元测试：骨架数值微调（不加护栏，None 沿用原型）。"""

from ai_rpg.models import Card, apply_numeric_design


def _card() -> Card:
    return Card(name="骨架", description="", cost=1, damage=2, hit_count=1, block=3)


def test_overrides_only_provided_fields() -> None:
    card = _card()
    apply_numeric_design(card, cost=0, damage=5, hit_count=2, block=0)
    assert (card.cost, card.damage, card.hit_count, card.block) == (0, 5, 2, 0)


def test_none_keeps_prototype_value() -> None:
    card = _card()
    apply_numeric_design(card, damage=7)
    assert (card.cost, card.damage, card.hit_count, card.block) == (1, 7, 1, 3)


def test_no_guardrails_on_values() -> None:
    # 不加护栏：负值（削减量）与 0 都原样写入。
    card = _card()
    apply_numeric_design(card, damage=-3, cost=0, block=-1)
    assert (card.cost, card.damage, card.block) == (0, -3, -1)
