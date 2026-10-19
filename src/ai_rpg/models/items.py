"""物品相关模型定义"""

from enum import StrEnum, unique
from typing import Annotated, List, Literal, Sequence, Union, final
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

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
    speed: int = 0  # 装备级被动速度修正，可正可负；装备登记期间累加进持有者有效速度
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
    """消耗品类，继承自物品基类。

    与 GearItem 对称：效果由内置卡牌承载（cards），战斗中物化为手牌后走普通出牌逻辑。
    消耗品卡固定 0 费（cost=0）且一次性（exhaust=True），由下方校验强制。
    """

    type: Literal[ItemType.CONSUMABLE_ITEM] = Field(
        default=ItemType.CONSUMABLE_ITEM, frozen=True
    )
    cards: List[Card] = (
        []
    )  # 内置卡牌列表：战斗中物化为手牌后正常打出；每张卡必须 cost=0 且 exhaust=True
    resources: Sequence["AnyItem"] = Field(
        default_factory=list
    )  # 合成时消耗的原料列表；未必是 MaterialItem（保留 AnyItem 扩展余地）

    @model_validator(mode="after")
    def _enforce_zero_cost_and_exhaust(self) -> "ConsumableItem":
        """消耗品卡固定 0 费且一次性：拦截 cost != 0 或 exhaust=False 的规格。"""
        for card in self.cards:
            if card.cost != 0:
                raise ValueError(
                    f"消耗品「{self.name}」的卡牌「{card.name}」cost 必须为 0（当前 {card.cost}）。"
                )
            if not card.exhaust:
                raise ValueError(
                    f"消耗品「{self.name}」的卡牌「{card.name}」必须 exhaust=True（一次性）。"
                )
        return self


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
