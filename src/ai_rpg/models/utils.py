"""models 层工具函数

提供基于组件数据的纯计算工具，不依赖 ECS Entity，便于单元测试与复用。
"""

from typing import List, Optional
from .cards import StatusEffect
from .components import CharacterStatsComponent, EquipmentComponent, InventoryComponent
from .items import WeaponItem, EquipmentItem
from .stats import CharacterStats


def compute_effective_stats(
    stats_comp: CharacterStatsComponent,
    equip_comp: Optional[EquipmentComponent],
    inventory_comp: Optional[InventoryComponent],
    status_effects: Optional[List[StatusEffect]] = None,
) -> CharacterStats:
    """计算角色的最终有效属性，聚合基础属性、已装备物品以及状态效果的属性加成。

    Args:
        stats_comp: 角色基础属性组件
        equip_comp: 装备槽组件，为 None 时不计算装备加成
        inventory_comp: 背包组件，为 None 时不计算装备加成
        status_effects: 当前状态效果列表，为 None 时不计算状态效果加成

    Returns:
        包含基础属性与所有加成之和的新 CharacterStats 实例
    """

    base = stats_comp.stats

    bonus_attack = 0
    bonus_defense = 0
    bonus_energy = 0
    bonus_speed = 0

    if equip_comp is not None and inventory_comp is not None:
        for slot_name in (
            equip_comp.weapon,
            equip_comp.armor,
            equip_comp.accessory,
        ):
            if not slot_name:
                continue
            for item in inventory_comp.items:
                if item.name != slot_name:
                    continue
                if isinstance(item, (WeaponItem, EquipmentItem)):
                    b = item.stat_bonuses
                    assert b.hp == 0, "当前设计中装备加成不应包含 HP 相关属性!"
                    bonus_attack += b.attack
                    bonus_defense += b.defense
                    bonus_energy += b.energy
                    bonus_speed += b.speed
                break

    for se in status_effects or []:
        bonus_speed += se.speed
        bonus_defense += se.defense

    return CharacterStats(
        hp=base.hp,
        max_hp=base.max_hp,
        attack=base.attack + bonus_attack,
        defense=base.defense + bonus_defense,
        energy=base.energy + bonus_energy,
        speed=base.speed + bonus_speed,
    )
