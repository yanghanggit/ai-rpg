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
class Item(BaseModel):
    """物品基类"""

    name: str
    description: str


###############################################################################################################################################
@final
class Inventory(BaseModel):
    """背包类"""

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
