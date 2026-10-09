"""库存道具堆叠与材料扣减纯函数的单元测试。

覆盖：
- append_item_with_stacking：材料按名称堆叠、消耗品按名称 + 效果提示词堆叠，装备不堆叠；
- merge_item_stacks：整表归一化；
- deduct_materials：跨同名条目结转，修复「第一个条目不足时少扣」的缺陷；
- consume_item_by_uuid：按 uuid 消耗一个数量（>1 递减、==1 移除），不就地修改。
"""

from typing import List

import pytest

from ai_rpg.models.items import (
    AnyItem,
    ConsumableItem,
    GearItem,
    MaterialItem,
)
from ai_rpg.models.utils import (
    append_item_with_stacking,
    consume_item_by_uuid,
    deduct_materials,
    merge_item_stacks,
)


def _consumable(name: str, prompt: str, count: int = 1) -> ConsumableItem:
    return ConsumableItem(name=name, description=f"{name} 的描述", on_use_prompt=[prompt], count=count)


def _material(name: str, count: int = 1) -> MaterialItem:
    return MaterialItem(name=name, description=f"{name} 的描述", count=count)


# ---------------------------------------------------------------------------
# append_item_with_stacking
# ---------------------------------------------------------------------------


def test_appends_consumable_to_empty_list() -> None:
    new_item = _consumable("消耗品.止血药粉", "恢复 3 点 HP。")

    result = append_item_with_stacking([], new_item)

    assert result == [new_item]
    assert result[0].count == 1


def test_consumable_stacks_same_name_and_prompt() -> None:
    existing = _consumable("消耗品.止血药粉", "恢复 3 点 HP。", count=2)
    new_item = _consumable("消耗品.止血药粉", "恢复 3 点 HP。", count=3)

    result = append_item_with_stacking([existing], new_item)

    assert len(result) == 1
    merged = result[0]
    assert isinstance(merged, ConsumableItem)
    assert merged.count == 5  # 累加 new_item.count，而非固定 +1
    assert merged.uuid == existing.uuid  # 保留旧条目身份


def test_consumable_same_name_different_prompt_not_stacked() -> None:
    existing = _consumable("消耗品.止血药粉", "恢复 3 点 HP。")
    new_item = _consumable("消耗品.止血药粉", "造成 2 点伤害。")

    result = append_item_with_stacking([existing], new_item)

    assert len(result) == 2


def test_material_stacks_by_name() -> None:
    existing = _material("材料.旧麻绳", count=2)
    new_item = _material("材料.旧麻绳", count=3)

    result = append_item_with_stacking([existing], new_item)

    assert len(result) == 1
    assert isinstance(result[0], MaterialItem)
    assert result[0].count == 5


def test_material_different_name_not_stacked() -> None:
    result = append_item_with_stacking(
        [_material("材料.旧麻绳", count=2)], _material("材料.铜质纽扣")
    )

    assert len(result) == 2


def test_does_not_mutate_inputs() -> None:
    existing = _material("材料.旧麻绳", count=2)
    original = [existing]

    append_item_with_stacking(original, _material("材料.旧麻绳", count=1))

    assert existing.count == 2
    assert len(original) == 1


def test_gear_never_stacks() -> None:
    existing = GearItem(name="装备.缠麻短刃", description="一柄短刃")
    new_item = GearItem(name="装备.缠麻短刃", description="一柄短刃")

    result = append_item_with_stacking([existing], new_item)

    assert len(result) == 2


def test_merges_into_first_matching_stack() -> None:
    first = _material("材料.旧麻绳", count=1)
    second = _material("材料.旧麻绳", count=5)
    new_item = _material("材料.旧麻绳", count=1)

    result = append_item_with_stacking([first, second], new_item)

    assert len(result) == 2
    assert result[0].count == 2  # 只并入第一个命中堆叠
    assert result[1].count == 5  # 其余堆叠不动


def test_returns_new_list_with_material_appended() -> None:
    items: List[AnyItem] = [_consumable("消耗品.止血药粉", "恢复 3 点 HP。")]

    result = append_item_with_stacking(items, _material("材料.旧麻绳"))

    assert result is not items
    assert len(result) == 2
    assert len(items) == 1


# ---------------------------------------------------------------------------
# merge_item_stacks
# ---------------------------------------------------------------------------


def test_merge_item_stacks_collapses_same_identity() -> None:
    items: List[AnyItem] = [
        _material("材料.旧麻绳", count=2),
        _consumable("消耗品.止血药粉", "恢复 3 点 HP。", count=1),
        _material("材料.旧麻绳", count=3),
        _consumable("消耗品.止血药粉", "恢复 3 点 HP。", count=2),
        GearItem(name="装备.缠麻短刃", description="一柄短刃"),
        GearItem(name="装备.缠麻短刃", description="一柄短刃"),
    ]

    result = merge_item_stacks(items)

    assert len(result) == 4  # 材料×1 + 消耗品×1 + 装备×2（装备不堆叠）
    assert isinstance(result[0], MaterialItem) and result[0].count == 5
    assert isinstance(result[1], ConsumableItem) and result[1].count == 3
    assert all(isinstance(item, GearItem) for item in result[2:])


# ---------------------------------------------------------------------------
# deduct_materials
# ---------------------------------------------------------------------------


def test_deduct_single_entry_partial() -> None:
    result = deduct_materials([_material("材料.旧麻绳", count=3)], ["材料.旧麻绳", "材料.旧麻绳"])

    assert len(result) == 1
    assert isinstance(result[0], MaterialItem)
    assert result[0].count == 1


def test_deduct_single_entry_exact_removes_entry() -> None:
    result = deduct_materials([_material("材料.旧麻绳", count=2)], ["材料.旧麻绳", "材料.旧麻绳"])

    assert result == []


def test_deduct_carries_remainder_across_duplicate_entries() -> None:
    """回归：第一个同名条目不足以覆盖需求时，余量必须结转到后续条目。"""

    items: List[AnyItem] = [_material("材料.符纸残片", count=1), _material("材料.符纸残片", count=3)]

    result = deduct_materials(items, ["材料.符纸残片", "材料.符纸残片"])

    assert len(result) == 1
    assert isinstance(result[0], MaterialItem)
    # 需求 2：第一条扣 1 后整条移除，余量 1 结转到第二条，剩 3 - 1 = 2
    assert result[0].count == 2


def test_deduct_keeps_unrelated_items() -> None:
    items: List[AnyItem] = [
        _material("材料.旧麻绳", count=5),
        _consumable("消耗品.止血药粉", "恢复 3 点 HP。", count=2),
    ]

    result = deduct_materials(items, ["材料.旧麻绳"])

    assert len(result) == 2
    materials = [i for i in result if isinstance(i, MaterialItem)]
    consumables = [i for i in result if isinstance(i, ConsumableItem)]
    assert materials[0].count == 4
    assert consumables[0].count == 2  # 同名消耗品不受材料扣减影响


def test_deduct_raises_when_demand_unmet() -> None:
    with pytest.raises(AssertionError):
        deduct_materials([_material("材料.旧麻绳", count=1)], ["材料.旧麻绳", "材料.旧麻绳"])


# ---------------------------------------------------------------------------
# consume_item_by_uuid
# ---------------------------------------------------------------------------


def test_consume_decrements_when_count_above_one() -> None:
    item = _consumable("消耗品.止血药粉", "恢复 3 点 HP。", count=2)

    result, consumed = consume_item_by_uuid([item], item.uuid)

    assert consumed is True
    assert len(result) == 1
    assert result[0].count == 1
    assert result[0].uuid == item.uuid
    assert item.count == 2  # 不就地修改原对象


def test_consume_removes_entry_when_last_count() -> None:
    item = _consumable("消耗品.止血药粉", "恢复 3 点 HP。", count=1)

    result, consumed = consume_item_by_uuid([item], item.uuid)

    assert consumed is True
    assert result == []


def test_consume_missing_uuid_returns_unchanged_flag_false() -> None:
    item = _consumable("消耗品.止血药粉", "恢复 3 点 HP。", count=2)

    result, consumed = consume_item_by_uuid([item], "不存在的-uuid")

    assert consumed is False
    assert result == [item]


def test_consume_only_first_matching_uuid() -> None:
    first = _consumable("消耗品.止血药粉", "恢复 3 点 HP。", count=2)
    second = _consumable("消耗品.止血药粉", "恢复 3 点 HP。", count=2)

    result, consumed = consume_item_by_uuid([first, second], first.uuid)

    assert consumed is True
    assert [i.count for i in result] == [1, 2]
