from enum import StrEnum, unique
from typing import List, final
from pydantic import BaseModel


###############################################################################################################################################
@final
class ActorCharacterSheet(BaseModel):
    """
    角色卡片定义
    包含角色的基本信息，如名称、类型、简介和外观描述等。
    这些信息用于描述角色的背景和特征，帮助玩家更好地理解角色在游戏中的定位和作用。
    """

    name: str
    type: str
    profile: str
    appearance: str


###############################################################################################################################################
@final
class StageCharacterSheet(BaseModel):
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
    NEUTRAL = "Neutral"  # 中立角色


###############################################################################################################################################
@final
@unique
class WerewolfCharacterSheetName(StrEnum):
    MODERATOR = "ww.moderator"
    WEREWOLF = "ww.werewolf"
    SEER = "ww.seer"
    WITCH = "ww.witch"
    VILLAGER = "ww.villager"
    HUNTER = "ww.hunter"


###############################################################################################################################################
@final
@unique
class WitchItemName(StrEnum):
    CURE = "道具.解药"
    POISON = "道具.毒药"


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
    experience: int = 0
    initial_level: int = 1
    hp: int = 0
    # 基础属性
    base_max_hp: int = 50
    base_strength: int = 5
    base_dexterity: int = 6
    base_wisdom: int = 5
    # 基础战斗属性
    base_physical_attack: int = 8
    base_physical_defense: int = 5
    base_magic_attack: int = 7
    base_magic_defense: int = 6
    # 成长系数
    strength_per_level: int = 2
    dexterity_per_level: int = 1
    wisdom_per_level: int = 1

    @property
    def max_hp(self) -> int:
        return self.base_max_hp + (self.strength * 10)

    @property
    def progression_level(self) -> int:
        return self.experience // 1000

    @property
    def level(self) -> int:
        return self.initial_level + self.progression_level

    @property
    def strength(self) -> int:
        return self.base_strength + (self.strength_per_level * self.progression_level)

    @property
    def dexterity(self) -> int:
        return self.base_dexterity + (self.dexterity_per_level * self.progression_level)

    @property
    def wisdom(self) -> int:
        return self.base_wisdom + (self.wisdom_per_level * self.progression_level)

    @property
    def physical_attack(self) -> int:
        return self.base_physical_attack + (self.strength * 2)

    @property
    def physical_defense(self) -> int:
        return self.base_physical_defense + self.strength

    @property
    def magic_attack(self) -> int:
        return self.base_magic_attack + (self.wisdom * 2)

    @property
    def magic_defense(self) -> int:
        return self.base_magic_defense + self.wisdom


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

    NONE = "None"
    WEAPON = "Weapon"
    ARMOR = "Armor"
    CONSUMABLE = "Consumable"
    MATERIAL = "Material"
    ACCESSORY = "Accessory"
    UNIQUE_ITEM = "UniqueItem"


###############################################################################################################################################
class Item(BaseModel):
    """物品基类"""

    name: str
    uuid: str
    type: ItemType
    description: str
    count: int = 1  # 物品数量，默认为1


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
    character_sheet: ActorCharacterSheet
    system_message: str
    kick_off_message: str
    character_stats: CharacterStats
    items: List[Item] = []
    skills: List[Skill] = []


###############################################################################################################################################
@final
class Stage(BaseModel):
    name: str
    character_sheet: StageCharacterSheet
    system_message: str
    kick_off_message: str
    actors: List[Actor]


###############################################################################################################################################
@final
class WorldSystem(BaseModel):
    name: str
    system_message: str
    kick_off_message: str


###############################################################################################################################################
