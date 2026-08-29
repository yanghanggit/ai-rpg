"""models 层工具函数

提供基于组件数据的纯计算工具，不依赖 ECS Entity，便于单元测试与复用。
"""

from typing import Optional
from .character_stats import CharacterStats
from .components import HandComponent


def compute_effective_stats(
    base_stats: CharacterStats,
    hand_component: Optional[HandComponent] = None,
) -> CharacterStats:
    """计算角色的最终有效属性，聚合基础属性与手牌格挡。"""

    bonus_defense = 0

    if hand_component is not None:
        bonus_defense += sum(card.block for card in hand_component.cards)

    return CharacterStats(
        hp=base_stats.hp,
        max_hp=base_stats.max_hp,
        attack=base_stats.attack,
        defense=base_stats.defense + bonus_defense,
    )
