from enum import StrEnum, unique
from typing import Dict, List, final
from uuid import uuid4
from pydantic import BaseModel, Field
from .assets_meta import AssetKey
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
    components: List[ComponentSerialization] = []
    assets: Dict[AssetKey, str] = Field(
        default_factory=dict
    )  # 场景插图等资源：AssetKey -> meta 路径（.assets/image/<file>.meta）


###############################################################################################################################################
@final
class World(BaseModel):
    name: str
    system_message: str
    components: List[ComponentSerialization] = []


###############################################################################################################################################
# Artifact / Artefact (神器/古物)：比“Relic”的使用更普遍，是许多游戏的标准命名之一。它强调物品的强大力量和古老属性，是品类里的“万金油”。
# 神器是第一公民实体：拥有独立名称、人设（system_message）与可挂载组件，由持有者实体通过 ReliquaryComponent 声明归属。
@final
class Artifact(BaseModel):
    """Artifact / Artefact (神器/古物)：独立实体，其人设即其作为 agent 的 system_message。"""

    name: str
    system_message: str
    modifiers: List[str] = []  # 对持有者或环境的属性修正列表
    components: List[ComponentSerialization] = []  # 挂载在神器上的组件序列化列表
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符
    assets: Dict[AssetKey, str] = Field(
        default_factory=dict
    )  # 场景插图等资源：AssetKey -> meta 路径（.assets/image/<file>.meta）


###############################################################################################################################################
