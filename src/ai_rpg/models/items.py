"""物品相关模型定义"""

from enum import StrEnum, unique
from typing import Annotated, List, Literal, Sequence, Union, final
from uuid import uuid4

from pydantic import BaseModel, Field

from .card import Card


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


###############################################################################################################################################
class GearItem(Item):
    """装备类（武器、防具、饰品等），继承自物品基类"""

    type: Literal[ItemType.GEAR_ITEM] = Field(default=ItemType.GEAR_ITEM, frozen=True)
    resources: Sequence["AnyItem"] = Field(
        default_factory=list
    )  # 合成时消耗的原料列表；未必是 MaterialItem（保留 AnyItem 扩展余地）
    cards: List[Card] = (
        []
    )  # GearItem => 可转化为手牌的卡牌列表；当前合成/蓝图仅放入 1 张，未来可支持多张


#######################################################################################################################################
class CostumeItem(Item):
    """时装类，仅改变角色外观（AppearanceComponent.appearance），不参与属性计算"""

    type: Literal[ItemType.COSTUME_ITEM] = Field(
        default=ItemType.COSTUME_ITEM, frozen=True
    )
    resources: Sequence["AnyItem"] = Field(
        default_factory=list
    )  # 合成时消耗的原料列表；未必是 MaterialItem（保留 AnyItem 扩展余地）


#######################################################################################################################################
class ConsumableItem(Item):
    """消耗品类，继承自物品基类"""

    type: Literal[ItemType.CONSUMABLE_ITEM] = Field(
        default=ItemType.CONSUMABLE_ITEM, frozen=True
    )
    on_use_prompt: List[str] = (
        []
    )  # 使用效果提示词列表；每个 str 是一条完整描述，当前使用 [0] 作为本次使用仲裁的完整效果提示（注入临时 agent）
    resources: Sequence["AnyItem"] = Field(
        default_factory=list
    )  # 合成时消耗的原料列表；未必是 MaterialItem（保留 AnyItem 扩展余地）


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

# 解决前向引用：AnyItem 定义后重新编译依赖它的三个模型
GearItem.model_rebuild()
CostumeItem.model_rebuild()
ConsumableItem.model_rebuild()


###############################################################################################################################################
