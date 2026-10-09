"""models 层工具函数

提供基于组件数据的纯计算工具，不依赖 ECS Entity，便于单元测试与复用。
"""

from typing import Dict, List, Optional, Tuple

from .card import Card
from .character_stats import CharacterStats
from .components import HandComponent
from .items import AnyItem, ConsumableItem, ItemType, MaterialItem


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


def _item_stack_key(item: AnyItem) -> Optional[Tuple[object, ...]]:
    """返回道具的堆叠身份键；不可堆叠的道具返回 None。

    堆叠规则的唯一定义处：材料按名称、消耗品按名称与效果提示词、装备/时装不堆叠。
    """
    if isinstance(item, MaterialItem):
        return (ItemType.MATERIAL_ITEM, item.name)
    if isinstance(item, ConsumableItem):
        return (ItemType.CONSUMABLE_ITEM, item.name, tuple(item.on_use_prompt))
    return None


def append_item_with_stacking(items: List[AnyItem], new_item: AnyItem) -> List[AnyItem]:
    """追加道具到库存列表并返回新列表；可堆叠道具并入已有同身份堆叠。

    不修改入参，也不就地改写命中的旧条目；命中堆叠时沿用旧条目其余字段与身份。
    """
    key = _item_stack_key(new_item)
    if key is not None:
        for index, item in enumerate(items):
            if _item_stack_key(item) == key:
                merged = item.model_copy(deep=True)
                merged.count += new_item.count
                updated = list(items)
                updated[index] = merged
                return updated
    return list(items) + [new_item]


def merge_item_stacks(items: List[AnyItem]) -> List[AnyItem]:
    """将一批道具归一化为无重复堆叠的列表，供写入库存前使用。

    保序（保留每类堆叠首次出现的位置）；不修改入参。
    """
    merged: List[AnyItem] = []
    for item in items:
        merged = append_item_with_stacking(merged, item)
    return merged


def deduct_materials(items: List[AnyItem], material_names: List[str]) -> List[AnyItem]:
    """按名称扣减材料并返回新列表；同一材料的多个条目会依次扣减，归零则移除。

    需求由 material_names 的出现次数统计；库存不足以满足需求时断言失败；不修改入参。
    """
    remaining: Dict[str, int] = {}
    for name in material_names:
        remaining[name] = remaining.get(name, 0) + 1

    updated: List[AnyItem] = []
    for item in items:
        if item.type == ItemType.MATERIAL_ITEM and remaining.get(item.name, 0) > 0:
            take = min(item.count, remaining[item.name])
            remaining[item.name] -= take
            left = item.count - take
            if left > 0:
                copied = item.model_copy(deep=True)
                copied.count = left
                updated.append(copied)
        else:
            updated.append(item)

    assert all(
        value == 0 for value in remaining.values()
    ), f"材料扣减未满足需求，剩余缺口: {remaining}"
    return updated


def consume_item_by_uuid(
    items: List[AnyItem], item_uuid: str
) -> Tuple[List[AnyItem], bool]:
    """按 uuid 消耗一个数量，返回（新列表, 是否命中）。

    仅命中首个匹配项，数量归零时移除该条目；不修改入参。
    """
    updated: List[AnyItem] = []
    consumed = False
    for item in items:
        if not consumed and item.uuid == item_uuid:
            consumed = True
            if item.count > 1:
                copied = item.model_copy(deep=True)
                copied.count -= 1
                updated.append(copied)
            # count == 1：归零，不追加（即从列表移除）
        else:
            updated.append(item)
    return updated, consumed


def apply_stats_to_card(card: Card, stats: CharacterStats) -> Card:
    """将角色属性叠加到卡牌上并返回该卡牌（原地修改）。

    规则：卡牌自身 damage/block 非 0 时，分别叠加角色的 attack/defense。
    """
    if card.damage != 0:
        card.damage += stats.attack
    if card.block != 0:
        card.block += stats.defense
    return card
