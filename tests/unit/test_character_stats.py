"""`CharacterStats` 与 `compute_effective_stats` 的单元测试。"""

from ai_rpg.models import CharacterStats
from ai_rpg.models.utils import compute_effective_stats


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
