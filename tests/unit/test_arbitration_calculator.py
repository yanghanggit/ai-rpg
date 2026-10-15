"""`arbitration_calculator` 纯计算单元测试。

覆盖骨架公式的代入、取整、逐击求和、clamp，以及展示片段与数值同源。
"""

from ai_rpg.systems.arbitration_calculator import compute_damage, compute_effects


class TestComputeDamage:
    def test_default_multipliers_single_hit(self) -> None:
        r = compute_damage(base_damage=5, hits=1, block=4, old_hp=20, max_hp=20)
        assert (r.hits, r.per_hit, r.total, r.new_hp) == (1, 1, 1, 19)
        assert r.expr == "5×1−4×1=每击1 ×1击=1"

    def test_block_fully_absorbs(self) -> None:
        r = compute_damage(base_damage=2, hits=1, block=4, old_hp=20, max_hp=20)
        assert (r.per_hit, r.total, r.new_hp) == (0, 0, 20)

    def test_multi_hit_sums_each_hit(self) -> None:
        r = compute_damage(base_damage=6, hits=2, block=4, old_hp=20, max_hp=20)
        assert (r.per_hit, r.total, r.new_hp) == (2, 4, 16)
        assert r.expr == "6×1−4×1=每击2 ×2击=4"

    def test_damage_multiplier_applied(self) -> None:
        r = compute_damage(
            base_damage=6, hits=2, block=4, old_hp=20, max_hp=20, damage_mult=2
        )
        assert (r.per_hit, r.total, r.new_hp) == (8, 16, 4)
        assert r.expr == "6×2−4×1=每击8 ×2击=16"

    def test_fractional_multiplier_rounds_half_up(self) -> None:
        r = compute_damage(
            base_damage=5, hits=1, block=0, old_hp=20, max_hp=20, damage_mult=1.5
        )
        assert r.per_hit == 8
        assert r.expr.startswith("5×1.5−0×1=每击8")

    def test_block_multiplier_zero_ignores_block(self) -> None:
        r = compute_damage(
            base_damage=5, hits=1, block=4, old_hp=20, max_hp=20, block_mult=0
        )
        assert (r.per_hit, r.total) == (5, 5)

    def test_clamped_at_zero(self) -> None:
        r = compute_damage(base_damage=10, hits=3, block=0, old_hp=5, max_hp=10)
        assert r.total == 30
        assert r.new_hp == 0

    def test_negative_coefficients_treated_as_zero(self) -> None:
        r = compute_damage(
            base_damage=5, hits=1, block=2, old_hp=20, max_hp=20, damage_mult=-1
        )
        assert r.per_hit == 0


class TestComputeEffects:
    def test_reflect_single_hit(self) -> None:
        r = compute_effects(base=2, hits=1, old_hp=10, max_hp=10, reflect_mult=1)
        assert (r.reflect, r.delta, r.new_hp) == (2, 2, 8)
        assert r.expr == "反伤2×1=2/击 ×1击=2 = 净扣减2"

    def test_reflect_multiplied_by_hit_count(self) -> None:
        r = compute_effects(base=3, hits=2, old_hp=10, max_hp=10, reflect_mult=1)
        assert (r.reflect, r.delta, r.new_hp) == (3, 6, 4)

    def test_lifesteal_heals_and_clamps_to_max(self) -> None:
        r = compute_effects(base=5, hits=1, old_hp=9, max_hp=10, lifesteal_mult=1)
        assert (r.lifesteal, r.delta, r.new_hp) == (5, -5, 10)
        assert r.expr == "吸血5×1=5/击 ×1击=5 = 净回复5"

    def test_fractional_heal_multiplier_rounds_half_up(self) -> None:
        r = compute_effects(base=5, hits=1, old_hp=10, max_hp=20, heal_mult=0.5)
        assert r.heal == 3
        assert r.expr == "治疗5×0.5=3/击 ×1击=3 = 净回复3"

    def test_net_zero_when_balanced(self) -> None:
        r = compute_effects(
            base=2, hits=1, old_hp=10, max_hp=10, reflect_mult=1, heal_mult=1
        )
        assert r.delta == 0
        assert r.new_hp == 10
        assert r.expr.endswith("= 0")

    def test_combined_components_expr(self) -> None:
        r = compute_effects(
            base=2, hits=1, old_hp=10, max_hp=20, reflect_mult=1, heal_mult=0.5
        )
        assert (r.reflect, r.heal, r.delta) == (2, 1, 1)
        assert r.expr == "反伤2×1=2/击 ×1击=2 治疗2×0.5=1/击 ×1击=1 = 净扣减1"

    def test_no_effect(self) -> None:
        r = compute_effects(base=0, hits=1, old_hp=10, max_hp=10)
        assert r.delta == 0
        assert r.new_hp == 10
        assert r.expr == "无 HP 变化"

    def test_negative_multipliers_treated_as_zero(self) -> None:
        r = compute_effects(base=5, hits=1, old_hp=10, max_hp=10, reflect_mult=-2)
        assert r.reflect == 0
        assert r.delta == 0
