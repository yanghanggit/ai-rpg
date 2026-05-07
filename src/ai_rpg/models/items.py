"""物品相关模型定义

包含物品枚举与物品基类及其子类：
ItemType、Item、WeaponItem、EquipmentType、EquipmentItem、
ConsumableItem、MaterialItem、UniqueItem、AnyItem。
"""

from enum import StrEnum, unique
from typing import Annotated, List, Literal, Union, final
from uuid import uuid4
from pydantic import BaseModel, Field
from .stats import CharacterStats
from .target_type import TargetType


###############################################################################################################################################
@final
@unique
class ItemType(StrEnum):
    """在游戏开发中，对类的命名通常会根据项目的规模和规范有所不同，但有一些常见的命名习惯。以下是一些常见的基类命名：

    物品基类：通常命名为 Item。这个基类会包含所有物品共有的属性和方法，如名称、描述、图标、ID等。

    武器/装备：武器和装备通常会有自己的子类。例如：

    武器：Weapon，继承自 Item

    装备：Equipment，也可能进一步分为 Armor（防具）、Accessory（饰品）等。

    消耗品：通常命名为 Consumable，继承自 Item。

    材料：通常命名为 Material，继承自 Item。

    珍贵物品：有时称为任务物品或独特物品，可能命名为 UniqueItem 或 QuestItem，继承自 Item。

    背包：背包通常是一个管理物品的容器，常见的命名有 Inventory（库存）或 Backpack。在代码中，我们通常使用 Inventory 来指代背包系统。"""

    WEAPON_ITEM = "WeaponItem"
    EQUIPMENT_ITEM = "EquipmentItem"
    CONSUMABLE_ITEM = "ConsumableItem"
    MATERIAL_ITEM = "MaterialItem"
    UNIQUE_ITEM = "UniqueItem"


###############################################################################################################################################
class Item(BaseModel):
    """物品基类"""

    name: str
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符
    description: str
    type: ItemType
    count: int = 1  # 物品数量，默认为1


#######################################################################################################################################
class WeaponItem(Item):
    """武器类，继承自物品基类"""

    type: Literal[ItemType.WEAPON_ITEM] = Field(
        default=ItemType.WEAPON_ITEM, frozen=True
    )
    stat_bonuses: CharacterStats = Field(
        default_factory=lambda: CharacterStats(
            hp=0, max_hp=0, attack=0, defense=0, energy=0, speed=0
        )
    )


###############################################################################################################################################
@final
@unique
class EquipmentType(StrEnum):
    """装备子类型，进一步细分装备的具体类别"""

    ARMOR = "Armor"  # 防具/全身套装（护甲、头盔、护腿等）
    ACCESSORY = "Accessory"  # 饰品（戒指、项链、护符等）
    NONE = "None"  # 未分类


#######################################################################################################################################
class EquipmentItem(Item):
    """装备类，继承自物品基类"""

    type: Literal[ItemType.EQUIPMENT_ITEM] = Field(
        default=ItemType.EQUIPMENT_ITEM, frozen=True
    )
    equipment_type: EquipmentType = EquipmentType.NONE  # 装备子类型
    stat_bonuses: CharacterStats = Field(
        default_factory=lambda: CharacterStats(
            hp=0, max_hp=0, attack=0, defense=0, energy=0, speed=0
        )
    )


#######################################################################################################################################
class ConsumableItem(Item):
    """消耗品类，继承自物品基类"""

    type: Literal[ItemType.CONSUMABLE_ITEM] = Field(
        default=ItemType.CONSUMABLE_ITEM, frozen=True
    )
    target_type: TargetType = TargetType.SELF_ONLY  # 使用目标类型，默认仅作用于自身
    effects: List[str] = []  # 潜在副作用词缀列表


#######################################################################################################################################
class MaterialItem(Item):
    """材料类，继承自物品基类"""

    type: Literal[ItemType.MATERIAL_ITEM] = Field(
        default=ItemType.MATERIAL_ITEM, frozen=True
    )


#######################################################################################################################################
class UniqueItem(Item):
    """珍贵物品类，继承自物品基类"""

    type: Literal[ItemType.UNIQUE_ITEM] = Field(
        default=ItemType.UNIQUE_ITEM, frozen=True
    )


###############################################################################################################################################
AnyItem = Annotated[
    Union[WeaponItem, EquipmentItem, ConsumableItem, MaterialItem, UniqueItem],
    Field(discriminator="type"),
]


###############################################################################################################################################
