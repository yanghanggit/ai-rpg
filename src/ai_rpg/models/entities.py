from enum import StrEnum, unique
from typing import List, final
from pydantic import BaseModel
from .serialization import ComponentSerialization
from .character_stats import CharacterStats


###############################################################################################################################################
@final
@unique
class ActorType(StrEnum):
    NONE = "None"
    NPC = "NPC"  # 我方/NPC/好人阵营
    MONSTER = "Monster"  # 敌方/怪物/坏人阵营


###############################################################################################################################################
@final
@unique
class StageType(StrEnum):
    NONE = "None"
    HOME = "Home"
    DUNGEON = "Dungeon"


###############################################################################################################################################
@final
class Actor(BaseModel):
    name: str
    type: ActorType
    profile: str
    base_body: str
    system_message: str
    character_stats: CharacterStats
    components: List[ComponentSerialization] = []


###############################################################################################################################################
@final
class Stage(BaseModel):
    name: str
    code_name: str  # 策划指定的英文代号（作为该场景动态组件类名的基准），必填
    type: StageType
    profile: str
    system_message: str
    actors: List[Actor]
    components: List[ComponentSerialization] = []


###############################################################################################################################################
@final
class World(BaseModel):
    name: str
    system_message: str
    components: List[ComponentSerialization] = []


###############################################################################################################################################
