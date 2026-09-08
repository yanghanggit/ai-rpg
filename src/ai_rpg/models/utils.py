"""models 层工具函数

提供基于组件数据的纯计算工具，不依赖 ECS Entity，便于单元测试与复用。
"""

from typing import Optional

from .card import Card
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


def apply_stats_to_card(card: Card, stats: CharacterStats) -> Card:
    """将角色属性叠加到卡牌上并返回该卡牌（原地修改）。

    规则：卡牌自身 damage/block 非 0 时，分别叠加角色的 attack/defense。
    """
    if card.damage != 0:
        card.damage += stats.attack
    if card.block != 0:
        card.block += stats.defense
    return card
