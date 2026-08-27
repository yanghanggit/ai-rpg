"""models 层工具函数

提供基于组件数据的纯计算工具，不依赖 ECS Entity，便于单元测试与复用。
"""

from typing import Optional
from .items import GearItem
from .character_stats import CharacterStats
from .components import HandComponent


def compute_effective_stats(
    base_stats: CharacterStats,
    equipped_gear: Optional[GearItem] = None,
    hand_component: Optional[HandComponent] = None,
) -> CharacterStats:
    """计算角色的最终有效属性，聚合基础属性、装备加成与手牌格挡。"""

    bonus_hp = 0
    bonus_max_hp = 0
    bonus_attack = 0
    bonus_defense = 0

    if equipped_gear is not None:
        bonus_hp += equipped_gear.stat_bonuses.hp
        bonus_max_hp += equipped_gear.stat_bonuses.max_hp
        bonus_attack += equipped_gear.stat_bonuses.attack
        bonus_defense += equipped_gear.stat_bonuses.defense

    if hand_component is not None:
        bonus_defense += sum(card.block for card in hand_component.cards)

    return CharacterStats(
        hp=base_stats.hp + bonus_hp,
        max_hp=base_stats.max_hp + bonus_max_hp,
        attack=base_stats.attack + bonus_attack,
        defense=base_stats.defense + bonus_defense,
    )
