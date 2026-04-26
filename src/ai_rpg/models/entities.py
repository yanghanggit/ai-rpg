from enum import IntEnum, StrEnum, unique
from typing import Annotated, List, Literal, Union, final
from pydantic import BaseModel, Field
from .serialization import ComponentSerialization


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
    max_hp: int = 10
    # 攻击力
    attack: int = 5
    # 防御力
    defense: int = 3
    # 每回合行动次数（能量）；决定该角色在 action_order 中出现几次，默认 1
    energy: int = 1
    # 速度；决定 SPEED_ORDER 策略下的出手优先级，值越大越靠前，默认 10
    speed: int = 10


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
@final
@unique
class DiceValue(IntEnum):
    """骰值范围常量（0-100 均匀随机整数）"""

    MIN = 0
    MAX = 100


###############################################################################################################################################
@final
class Archetype(BaseModel):
    """卡牌原型，定义角色生成卡牌时遵循的风格与功能约束。

    通过自然语言描述约束规则，LLM 在生成卡牌时据此限制生成边界。
    空列表表示无约束，角色可自由生成任意风格的卡牌。

    Attributes:
        description: 约束规则的自然语言描述
    """

    description: str


###############################################################################################################################################
@final
class Actor(BaseModel):
    name: str
    character_sheet: CharacterSheet
    system_message: str
    character_stats: CharacterStats
    items: List[AnyItem] = []
    archetypes: List[Archetype] = (
        []
    )  # 卡牌原型约束列表，用于限制 LLM 生成卡牌的风格与功能边界


###############################################################################################################################################
@final
class Stage(BaseModel):
    name: str
    stage_profile: StageProfile
    system_message: str
    actors: List[Actor]


###############################################################################################################################################
@final
class WorldSystem(BaseModel):
    name: str
    system_message: str
    components: List[ComponentSerialization] = []


###############################################################################################################################################
