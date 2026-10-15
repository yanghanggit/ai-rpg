"""仲裁纯计算模块（不依赖游戏对象）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MINUS = "−"  # U+2212，与 combat_log 既有风格一致
DEFAULT_MULT = 1.0


def _round_half_up(value: float) -> int:
    """四舍五入（half-up），用于把倍率代入后的数值取整。"""
    return int(math.floor(value + 0.5))


def _fmt_mult(value: float) -> str:
    """倍率展示：整数值去掉小数点（如 1.0 → 1）。"""
    return str(int(value)) if float(value).is_integer() else str(value)


#######################################################################################################################################
# 承伤（过格挡）
#######################################################################################################################################
@dataclass(frozen=True)
class DamageResult:
    """一次「承伤」结算结果。`total` 即目标 HP 的净减少量。"""

    hits: int
    per_hit: int
    total: int
    new_hp: int
    expr: str


def compute_damage(
    *,
    base_damage: int,
    hits: int,
    block: int,
    old_hp: int,
    max_hp: int,
    damage_mult: float = DEFAULT_MULT,
    block_mult: float = DEFAULT_MULT,
) -> DamageResult:
    """按骨架公式结算承伤。

    `命中伤害 = max(0, base_damage × damage_mult − block × block_mult)`，逐击求和；
    倍率代入后按四舍五入取整。
    """
    hits = max(0, int(hits))
    damage_mult = max(0.0, float(damage_mult))
    block_mult = max(0.0, float(block_mult))
    effective_damage = _round_half_up(max(0, int(base_damage)) * damage_mult)
    effective_block = _round_half_up(max(0, int(block)) * block_mult)
    per_hit = max(0, effective_damage - effective_block)
    total = per_hit * hits
    new_hp = max(0, min(int(old_hp) - total, int(max_hp)))
    expr = (
        f"{base_damage}×{_fmt_mult(damage_mult)}{MINUS}{block}×{_fmt_mult(block_mult)}"
        f"=每击{per_hit} ×{hits}击={total}"
    )
    return DamageResult(
        hits=hits, per_hit=per_hit, total=total, new_hp=new_hp, expr=expr
    )


#######################################################################################################################################
# 受效（反伤 / 吸血 / 治疗，不过格挡）
#######################################################################################################################################
@dataclass(frozen=True)
class EffectResult:
    """一次「受效」结算结果。`delta` 为净扣减（>0 扣血，<0 净回复）。"""

    hits: int
    reflect: int
    lifesteal: int
    heal: int
    delta: int
    new_hp: int
    expr: str


def compute_effects(
    *,
    base: int,
    hits: int,
    old_hp: int,
    max_hp: int,
    reflect_mult: float = 0.0,
    lifesteal_mult: float = 0.0,
    heal_mult: float = 0.0,
) -> EffectResult:
    """按每击结算某受效角色的反伤 / 吸血 / 治疗。

    各分量 `= 四舍五入(base × 对应倍率)`；`净扣减 = (反伤 − 吸血 − 治疗) × hits`。
    """
    base = int(base)
    hits = max(0, int(hits))
    reflect_mult = max(0.0, float(reflect_mult))
    lifesteal_mult = max(0.0, float(lifesteal_mult))
    heal_mult = max(0.0, float(heal_mult))
    reflect = _round_half_up(base * reflect_mult)
    lifesteal = _round_half_up(base * lifesteal_mult)
    heal = _round_half_up(base * heal_mult)
    delta = (reflect - lifesteal - heal) * hits
    new_hp = max(0, min(int(old_hp) - delta, int(max_hp)))
    parts: list[str] = []
    if reflect:
        parts.append(
            f"反伤{base}×{_fmt_mult(reflect_mult)}={reflect}/击 ×{hits}击={reflect * hits}"
        )
    if lifesteal:
        parts.append(
            f"吸血{base}×{_fmt_mult(lifesteal_mult)}={lifesteal}/击 ×{hits}击={lifesteal * hits}"
        )
    if heal:
        parts.append(
            f"治疗{base}×{_fmt_mult(heal_mult)}={heal}/击 ×{hits}击={heal * hits}"
        )
    if not parts:
        expr = "无 HP 变化"
    elif delta > 0:
        expr = " ".join(parts) + f" = 净扣减{delta}"
    elif delta < 0:
        expr = " ".join(parts) + f" = 净回复{-delta}"
    else:
        expr = " ".join(parts) + " = 0"
    return EffectResult(
        hits=hits,
        reflect=reflect,
        lifesteal=lifesteal,
        heal=heal,
        delta=delta,
        new_hp=new_hp,
        expr=expr,
    )
