from enum import StrEnum, unique
from typing import List, final
from pydantic import BaseModel, Field


###############################################################################################################################################
@final
class CharacterSheet(BaseModel):
    """
    角色卡片定义
    包含角色的基本信息，如名称、类型、简介和外观描述等。
    这些信息用于描述角色的背景和特征，帮助玩家更好地理解角色在游戏中的定位和作用。
    """

    name: str
    type: str
    profile: str
    base_body: str
    appearance: str


###############################################################################################################################################
@final
class StageProfile(BaseModel):
    """
    场景卡片定义
    包含场景的基本信息，如名称、类型和简介等。
    这些信息用于描述场景的背景和特征，帮助玩家更好地理解场景在游戏中的定位和作用。
    """

    name: str
    type: str
    profile: str


###############################################################################################################################################
@final
@unique
class ActorType(StrEnum):
    NONE = "None"
    ALLY = "Ally"  # 我方/盟友/好人阵营
    ENEMY = "Enemy"  # 敌方/怪物/坏人阵营
    # NEUTRAL = "Neutral"  # 中立角色


###############################################################################################################################################
@final
@unique
class StageType(StrEnum):
    NONE = "None"
    HOME = "Home"
    DUNGEON = "Dungeon"


###############################################################################################################################################
@final
class CharacterStats(BaseModel):
    """简化的角色属性统计，只包含核心战斗属性"""

    # 当前生命值
    hp: int = 0
    # 最大生命值
    max_hp: int = 50
    # 攻击力
    attack: int = 10
    # 防御力
    defense: int = 5


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
    uuid: str
    description: str
    type: ItemType
    count: int = 1  # 物品数量，默认为1


#######################################################################################################################################
class WeaponItem(Item):
    """武器类，继承自物品基类"""

    type: ItemType = Field(default=ItemType.WEAPON_ITEM, frozen=True)


#######################################################################################################################################
class EquipmentItem(Item):
    """装备类，继承自物品基类"""

    type: ItemType = Field(default=ItemType.EQUIPMENT_ITEM, frozen=True)


#######################################################################################################################################
class ConsumableItem(Item):
    """消耗品类，继承自物品基类"""

    type: ItemType = Field(default=ItemType.CONSUMABLE_ITEM, frozen=True)


#######################################################################################################################################
class MaterialItem(Item):
    """材料类，继承自物品基类"""

    type: ItemType = Field(default=ItemType.MATERIAL_ITEM, frozen=True)


#######################################################################################################################################
class UniqueItem(Item):
    """珍贵物品类，继承自物品基类"""

    type: ItemType = Field(default=ItemType.UNIQUE_ITEM, frozen=True)


#######################################################################################################################################
# 技能定义
@final
class Skill(BaseModel):
    name: str  # 技能名称
    description: str  # 技能描述


###############################################################################################################################################
@final
class Actor(BaseModel):
    name: str
    character_sheet: CharacterSheet
    system_message: str
    kick_off_message: str
    character_stats: CharacterStats
    items: List[Item] = []
    skills: List[Skill] = []
    # private_knowledge: List[str] = []


###############################################################################################################################################
@final
class Stage(BaseModel):
    name: str
    stage_profile: StageProfile
    system_message: str
    kick_off_message: str
    actors: List[Actor]


###############################################################################################################################################
@final
class WorldSystem(BaseModel):
    name: str
    system_message: str
    kick_off_message: str
    component: str


###############################################################################################################################################
