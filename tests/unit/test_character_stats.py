"""`CharacterStats` 与 `compute_effective_stats` 的单元测试。"""

from ai_rpg.models import CharacterStats, EquippedGearComponent, GearItem
from ai_rpg.models.utils import compute_effective_stats


def _gear(speed: int) -> GearItem:
    return GearItem(name="装备.测试", description="测试装备", speed=speed)


def test_speed_defaults_to_zero() -> None:
    assert CharacterStats().speed == 0


def test_compute_effective_stats_preserves_all_fields_including_speed() -> None:
    stats = CharacterStats(hp=3, max_hp=8, attack=2, defense=1, speed=7)

    effective = compute_effective_stats(stats)

    assert effective == stats
    assert effective.speed == 7


def test_compute_effective_stats_returns_independent_copy() -> None:
    stats = CharacterStats(speed=4)

    effective = compute_effective_stats(stats)
    effective.speed = 9

    assert stats.speed == 4


def test_compute_effective_stats_sums_equipped_gear_speed() -> None:
    stats = CharacterStats(attack=3, defense=1, speed=5)
    gear = EquippedGearComponent(
        name="角色.测试", items=[_gear(1), _gear(-2), _gear(3)]
    )

    effective = compute_effective_stats(stats, gear)

    assert effective.speed == 5 + 1 - 2 + 3
    # 基础属性不被就地修改（保真、可重复调用）
    assert stats.speed == 5


def test_compute_effective_stats_without_gear_keeps_base_speed() -> None:
    stats = CharacterStats(speed=5)

    assert compute_effective_stats(stats).speed == 5
    assert compute_effective_stats(stats, None).speed == 5


def test_compute_effective_stats_gear_does_not_touch_attack_defense() -> None:
    # 装备的 damage / block 已由卡牌通道承载，装备级被动只影响 speed。
    stats = CharacterStats(attack=3, defense=1, speed=0)
    gear = EquippedGearComponent(name="角色.测试", items=[_gear(2)])

    effective = compute_effective_stats(stats, gear)

    assert effective.attack == 3
    assert effective.defense == 1
