"""models 层工具函数

提供基于组件数据的纯计算工具，不依赖 ECS Entity，便于单元测试与复用。
"""

from typing import Optional

from .character_stats import CharacterStats
from .components import HandComponent


def compute_effective_stats(base_stats: CharacterStats) -> CharacterStats:
    """返回角色的基础属性（当前不做任何加成，仅作副本返回）。"""

    return CharacterStats(
        hp=base_stats.hp,
        max_hp=base_stats.max_hp,
        attack=base_stats.attack,
        defense=base_stats.defense,
    )


def compute_hand_block(hand_component: Optional[HandComponent]) -> int:
    """计算手牌提供的总格挡（block 之和）。"""
    if hand_component is None:
        return 0
    return sum(card.block for card in hand_component.cards)
