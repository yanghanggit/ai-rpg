from enum import StrEnum, unique
from typing import List, final
from pydantic import BaseModel
from .character_sheet import ActorCharacterSheet, StageCharacterSheet


###############################################################################################################################################
@final
@unique
class ActorType(StrEnum):
    NONE = "None"
    HERO = "Hero"
    MONSTER = "Monster"


###############################################################################################################################################
@final
@unique
class SDCharacterSheetName(StrEnum):
    MODERATOR = "sd.moderator"
    WEREWOLF = "sd.werewolf"
    SEER = "sd.seer"
    WITCH = "sd.witch"
    VILLAGER = "sd.villager"
    GUARD = "sd.guard"


###############################################################################################################################################
@final
@unique
class SDWitchItemName(StrEnum):
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
class RPGCharacterProfile(BaseModel):
    experience: int = 0
    fixed_level: int = 1
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

    def add_experience(self, exp: int) -> None:
        self.experience += exp

    @property
    def max_hp(self) -> int:
        return self.base_max_hp + (self.strength * 10)

    @property
    def progression_level(self) -> int:
        return self.experience // 1000

    @property
    def level(self) -> int:
        return self.fixed_level + self.progression_level

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


# 写一个方法，将RPGCharacterProfile的所有属性（包括@property的），生成一个str。
def generate_character_profile_string(
    rpg_character_profile: RPGCharacterProfile,
) -> str:
    attributes = [
        "hp",
        "max_hp",
        "level",
        "experience",
        "strength",
        "dexterity",
        "wisdom",
        "physical_attack",
        "physical_defense",
        "magic_attack",
        "magic_defense",
        # "base_max_hp",
        # "base_strength",
        # "base_dexterity",
        # "base_wisdom",
        # "base_physical_attack",
        # "base_physical_defense",
        # "base_magic_attack",
        # "base_magic_defense",
        # "strength_per_level",
        # "dexterity_per_level",
        # "wisdom_per_level",
        # "fixed_level",
        # "progression_level",
        # "strength_per_level",
        # "dexterity_per_level",
        # "wisdom_per_level",
    ]
    result = []
    for attr in attributes:
        value = getattr(rpg_character_profile, attr)
        result.append(f"{attr}: {value}")
    return "\n".join(result)


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


###############################################################################################################################################
@final
class Inventory(BaseModel):
    """背包类，包含多个物品"""

    items: List[Item] = []


###############################################################################################################################################
@final
class Actor(BaseModel):
    name: str
    character_sheet: ActorCharacterSheet
    system_message: str
    kick_off_message: str
    rpg_character_profile: RPGCharacterProfile
    inventory: Inventory


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
