"""models 层工具函数

提供基于组件数据的纯计算工具，不依赖 ECS Entity，便于单元测试与复用。
"""

from typing import List, Optional
from .cards import StatusEffect
from .items import GearItem
from .stats import CharacterStats


def compute_effective_stats(
    base_stats: CharacterStats,
    status_effects: Optional[List[StatusEffect]] = None,
    equipped_gear: Optional[GearItem] = None,
) -> CharacterStats:
    """计算角色的最终有效属性，聚合基础属性与状态效果的属性加成。

    Args:
        base_stats: 角色的基础属性
        status_effects: 当前状态效果列表，为 None 时不计算状态效果加成

    Returns:
        包含基础属性与所有加成之和的新 CharacterStats 实例
    """

    bonus_hp = 0
    bonus_max_hp = 0
    bonus_attack = 0
    bonus_defense = 0
    bonus_energy = 0
    bonus_speed = 0

    if equipped_gear is not None:
        bonus_hp += equipped_gear.stat_bonuses.hp
        bonus_max_hp += equipped_gear.stat_bonuses.max_hp
        bonus_attack += equipped_gear.stat_bonuses.attack
        bonus_defense += equipped_gear.stat_bonuses.defense
        bonus_energy += equipped_gear.stat_bonuses.energy
        bonus_speed += equipped_gear.stat_bonuses.speed

    for se in status_effects or []:
        bonus_speed += se.speed
        bonus_defense += se.defense

    assert (
        bonus_hp == 0
    ), "当前设计中状态效果不应直接修改 HP，若需要请改为修改 max_hp 或通过其他机制实现"
    return CharacterStats(
        hp=base_stats.hp + bonus_hp,
        max_hp=base_stats.max_hp + bonus_max_hp,
        attack=base_stats.attack + bonus_attack,
        defense=base_stats.defense + bonus_defense,
        energy=base_stats.energy + bonus_energy,
        speed=base_stats.speed + bonus_speed,
    )
