from typing import List, final
from pydantic import BaseModel
from enum import StrEnum, unique
from .database import ActorPrototype, StagePrototype
from .registry import register_base_model_class


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
# Max HP            = 50 + (10 × STR)
# Physical Attack   = 5  + (2  × STR)
# Physical Defense  = 5  + (1  × STR)
# Magic Attack      = 5  + (2  × WIS)
# Magic Defense     = 5  + (1  × WIS)
# Accuracy          = 5  + (2  × DEX)
# Evasion           = 5  + (1  × DEX)
###############################################################################################################################################
@final
@register_base_model_class
class BaseAttributes(BaseModel):
    hp: int = 0
    strength: int
    dexterity: int
    wisdom: int

    @property
    def max_hp(self) -> int:
        return 50 + (10 * self.strength)

    @property
    def physical_attack(self) -> int:
        return 5 + (2 * self.strength)

    @property
    def physical_defense(self) -> int:
        return 5 + (1 * self.strength)

    @property
    def magic_attack(self) -> int:
        return 5 + (2 * self.wisdom)

    @property
    def magic_defense(self) -> int:
        return 5 + (1 * self.wisdom)


###############################################################################################################################################
@final
@register_base_model_class
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


###############################################################################################################################################
@final
@register_base_model_class
class Actor(BaseModel):
    name: str
    prototype: ActorPrototype
    system_message: str
    kick_off_message: str
    base_attributes: BaseAttributes


###############################################################################################################################################
@final
@register_base_model_class
class Stage(BaseModel):
    name: str
    prototype: StagePrototype
    system_message: str
    kick_off_message: str
    actors: List[Actor]


###############################################################################################################################################
@final
@register_base_model_class
class WorldSystem(BaseModel):
    name: str
    system_message: str
    kick_off_message: str


###############################################################################################################################################
