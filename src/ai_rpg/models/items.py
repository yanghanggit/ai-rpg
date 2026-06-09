"""物品相关模型定义

包含物品枚举与物品基类及其子类：
ItemType、Item、GearItem、CostumeItem、ConsumableItem、MaterialItem、AnyItem。
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

    GEAR_ITEM = "GearItem"
    COSTUME_ITEM = "CostumeItem"
    CONSUMABLE_ITEM = "ConsumableItem"
    MATERIAL_ITEM = "MaterialItem"


###############################################################################################################################################
class Item(BaseModel):
    """物品基类"""

    name: str
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符
    description: str
    type: ItemType
    count: int = 1  # 物品数量，默认为1


#######################################################################################################################################
@final
@unique
class GearCategory(StrEnum):
    """三种功能性装备类别：武器、盔甲、饰品"""

    WEAPON = "weapon"  # 武器
    ARMOR = "armor"  # 盔甲
    ACCESSORY = "accessory"  # 饰品


###############################################################################################################################################
class GearItem(Item):
    """装备类（武器、防具、饰品等），继承自物品基类"""

    type: Literal[ItemType.GEAR_ITEM] = Field(default=ItemType.GEAR_ITEM, frozen=True)
    gear_slot: GearCategory  # 装备槽位
    stat_bonuses: CharacterStats = Field(
        default_factory=lambda: CharacterStats(
            hp=0, max_hp=0, attack=0, defense=0, energy=0, speed=0
        )
    )
    affixes: List[str] = []  # 延迟词缀列表（同 Card.affixes）
    modifiers: List[str] = []  # 即时修正词缀列表（同 Card.modifiers）


#######################################################################################################################################
class CostumeItem(Item):
    """时装类，仅改变角色外观（AppearanceComponent.appearance），不参与属性计算"""

    type: Literal[ItemType.COSTUME_ITEM] = Field(
        default=ItemType.COSTUME_ITEM, frozen=True
    )


#######################################################################################################################################
class ConsumableItem(Item):
    """消耗品类，继承自物品基类"""

    type: Literal[ItemType.CONSUMABLE_ITEM] = Field(
        default=ItemType.CONSUMABLE_ITEM, frozen=True
    )
    target_type: TargetType = TargetType.SELF_ONLY  # 使用目标类型，默认仅作用于自身
    affixes: List[str] = []  # 潜在副作用词缀列表


#######################################################################################################################################
class MaterialItem(Item):
    """材料类，继承自物品基类"""

    type: Literal[ItemType.MATERIAL_ITEM] = Field(
        default=ItemType.MATERIAL_ITEM, frozen=True
    )


###############################################################################################################################################
AnyItem = Annotated[
    Union[GearItem, CostumeItem, ConsumableItem, MaterialItem],
    Field(discriminator="type"),
]


###############################################################################################################################################
