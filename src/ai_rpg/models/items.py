"""物品相关模型定义"""

from enum import StrEnum, unique
from typing import Annotated, List, Literal, Sequence, Union, final
from uuid import uuid4
from pydantic import BaseModel, Field
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


###############################################################################################################################################
class GearItem(Item):
    """装备类（武器、防具、饰品等），继承自物品基类"""

    type: Literal[ItemType.GEAR_ITEM] = Field(default=ItemType.GEAR_ITEM, frozen=True)
    resources: Sequence["AnyItem"] = Field(
        default_factory=list
    )  # 合成时消耗的原料列表；未必是 MaterialItem（保留 AnyItem 扩展余地）
    keywords: List[str] = (
        []
    )  # GearItem => Card 时的功能边界约束/指导词；空表示无额外约束


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
    target_type: TargetType = TargetType.SINGLE  # 使用目标类型，默认作用于单个角色
    on_use_affixes: List[str] = (
        []
    )  # 即时词缀列表；格式"[名称]:触发倾向描述"（如"[穿透]:本次使用无视目标防御"）；参与本次使用仲裁，由仲裁 LLM 直接套用；无即时效果时输出 []
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
