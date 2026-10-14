from enum import StrEnum, unique
from typing import Dict, List, final

from pydantic import BaseModel, Field

from ..entitas import EntityData
from .assets_meta import AssetKey
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
    components: EntityData = {}
    assets: Dict[AssetKey, str] = Field(
        default_factory=dict
    )  # 场景插图等资源：AssetKey -> meta 路径（.assets/image/<file>.meta）


###############################################################################################################################################
@final
class Stage(BaseModel):
    name: str
    type: StageType
    profile: str
    system_message: str
    actors: List[Actor]
    components: EntityData = {}
    assets: Dict[AssetKey, str] = Field(
        default_factory=dict
    )  # 场景插图等资源：AssetKey -> meta 路径（.assets/image/<file>.meta）


###############################################################################################################################################
@final
class World(BaseModel):
    name: str
    system_message: str
    components: EntityData = {}


###############################################################################################################################################
