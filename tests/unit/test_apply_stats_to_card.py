"""`apply_stats_to_card` 的单元测试。

`damage` / `block` 为正数时分别随角色 `attack` / `defense` 成长；0 表示不承
载该类数值；为负表示「削减量」（如传给对方的破甲牌），是 debuff 幅度，不随持有
者属性变化。
"""

from ai_rpg.models import Card, CharacterStats, apply_stats_to_card


def _stats() -> CharacterStats:
    return CharacterStats(attack=3, defense=2)


def test_positive_damage_and_block_scale_with_stats() -> None:
    card = Card(name="基础攻击", description="", damage=2, block=1)

    apply_stats_to_card(card, _stats())

    assert card.damage == 5  # 2 + attack(3)
    assert card.block == 3  # 1 + defense(2)


def test_zero_values_stay_zero() -> None:
    card = Card(name="纯状态牌", description="", damage=0, block=0)

    apply_stats_to_card(card, _stats())

    assert card.damage == 0
    assert card.block == 0


def test_negative_block_is_debuff_not_scaled() -> None:
    # 负 block = 削减量（破甲牌传给对方），不叠加持有者防御。
    card = Card(name="破甲", description="", block=-3, transferable=True)

    apply_stats_to_card(card, _stats())

    assert card.block == -3


def test_negative_damage_is_debuff_not_scaled() -> None:
    # 负 damage = 削减量，同样不叠加持有者攻击（与负 block 对齐）。
    card = Card(name="破伤", description="", damage=-2, transferable=True)

    apply_stats_to_card(card, _stats())

    assert card.damage == -2
