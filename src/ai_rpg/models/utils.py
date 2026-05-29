"""models 层工具函数

提供基于组件数据的纯计算工具，不依赖 ECS Entity，便于单元测试与复用。
"""

from typing import List, Optional
from .cards import StatusEffect
from .components import CharacterStatsComponent
from .stats import CharacterStats


def compute_effective_stats(
    stats_comp: CharacterStatsComponent,
    status_effects: Optional[List[StatusEffect]] = None,
) -> CharacterStats:
    """计算角色的最终有效属性，聚合基础属性与状态效果的属性加成。

    Args:
        stats_comp: 角色基础属性组件
        status_effects: 当前状态效果列表，为 None 时不计算状态效果加成

    Returns:
        包含基础属性与所有加成之和的新 CharacterStats 实例
    """

    base = stats_comp.stats

    bonus_defense = 0
    bonus_speed = 0

    for se in status_effects or []:
        bonus_speed += se.speed
        bonus_defense += se.defense

    return CharacterStats(
        hp=base.hp,
        max_hp=base.max_hp,
        attack=base.attack,
        defense=base.defense + bonus_defense,
        energy=base.energy,
        speed=base.speed + bonus_speed,
    )
