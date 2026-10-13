"""models 层工具函数

提供基于组件数据的纯计算工具，不依赖 ECS Entity，便于单元测试与复用。
"""

from typing import Dict, List, Optional, Tuple

from .card import Card
from .character_stats import CharacterStats
from .components import HandComponent
from .items import AnyItem, ConsumableItem, ItemType, MaterialItem
from .str_list import normalize_str_list


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


def _item_stack_key(item: AnyItem) -> Optional[Tuple[ItemType, str, Tuple[str, ...]]]:
    """返回道具的堆叠身份键；不可堆叠的道具返回 None。

    堆叠规则的唯一定义处：材料按名称、消耗品按名称与效果提示词、装备/时装不堆叠。
    """
    if isinstance(item, MaterialItem):
        # 材料没有额外堆叠维度，第三位用空元组占位，与消耗品保持同构的三元组键。
        return (ItemType.MATERIAL_ITEM, item.name, ())
    if isinstance(item, ConsumableItem):
        # 多值效果提示：全部元素参与堆叠身份（与仲裁逐条全部结算保持一致）。
        return (
            ItemType.CONSUMABLE_ITEM,
            item.name,
            tuple(normalize_str_list(item.on_use_prompt)),
        )
    return None


def append_item_with_stacking(items: List[AnyItem], new_item: AnyItem) -> List[AnyItem]:
    """追加道具到库存列表并返回新列表；可堆叠道具并入已有同身份堆叠。

    不修改入参，也不就地改写命中的旧条目；命中堆叠时沿用旧条目其余字段与身份。
    """
    key = _item_stack_key(new_item)
    if key is not None:

        # 尝试在已有堆叠中寻找可合并的条目
        for index, item in enumerate(items):

            # 检查当前条目是否与新道具的堆叠身份键匹配
            if _item_stack_key(item) == key:

                # 找到可合并的堆叠条目，创建其深拷贝并增加数量
                merged = item.model_copy(deep=True)
                merged.count += new_item.count
                updated = list(items)
                updated[index] = merged
                return updated

    # 没有找到可合并的堆叠条目，直接追加新道具
    return list(items) + [new_item]


def merge_item_stacks(items: List[AnyItem]) -> List[AnyItem]:
    """将一批道具归一化为无重复堆叠的列表，供写入库存前使用。

    保序（保留每类堆叠首次出现的位置）；不修改入参。
    """
    merged: List[AnyItem] = []
    for item in items:
        # 将当前道具尝试合并到已有堆叠中，如果无法合并则直接追加
        merged = append_item_with_stacking(merged, item)

    return merged


def deduct_materials(items: List[AnyItem], material_names: List[str]) -> List[AnyItem]:
    """按名称扣减材料并返回新列表；同一材料的多个条目会依次扣减，归零则移除。

    需求由 material_names 的出现次数统计；库存不足以满足需求时断言失败；不修改入参。
    """
    remaining: Dict[str, int] = {}
    for name in material_names:
        # 统计每种材料的需求数量
        remaining[name] = remaining.get(name, 0) + 1

    updated: List[AnyItem] = []
    for item in items:

        # 如果当前条目是材料且仍有剩余需求，则按数量扣减
        if item.type == ItemType.MATERIAL_ITEM and remaining.get(item.name, 0) > 0:
            take = min(item.count, remaining[item.name])
            remaining[item.name] -= take
            left = item.count - take

            # 如果扣减后仍有剩余数量，则创建其深拷贝并更新数量，追加到结果列表中
            if left > 0:
                copied = item.model_copy(deep=True)
                copied.count = left
                updated.append(copied)
        else:

            # 当前条目不是材料或已满足需求，直接追加到结果列表中
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
            # 命中首个匹配项，数量减 1 或移除
            consumed = True
            if item.count > 1:
                copied = item.model_copy(deep=True)
                copied.count -= 1
                updated.append(copied)

            # count == 1：归零，不追加（即从列表移除）
        else:
            updated.append(item)

    # 返回更新后的列表和是否命中标志
    return updated, consumed


def apply_stats_to_card(card: Card, stats: CharacterStats) -> Card:
    """将角色属性叠加到卡牌上并返回该卡牌（原地修改）。

    规则：`damage` / `block` **为正数**时分别叠加角色 `attack` / `defense`；
    为 0 表示不承载该类数值；为负表示「削减量」（如传给对方的破甲牌），是 debuff
    幅度，不随持有者属性变化，原样保留。
    """

    # 仅在 damage 为正数时叠加角色攻击
    if card.damage > 0:
        card.damage += stats.attack

    # 仅在 block 为正数时叠加角色防御
    if card.block > 0:
        card.block += stats.defense
    return card
