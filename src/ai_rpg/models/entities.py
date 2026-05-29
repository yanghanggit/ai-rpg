from enum import StrEnum, unique
from typing import List, final
from pydantic import BaseModel
from .serialization import ComponentSerialization
from .stats import CharacterStats
from .cards import Keyword


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
    character_sheet: CharacterSheet
    system_message: str
    character_stats: CharacterStats
    keywords: List[Keyword] = (
        []
    )  # 卡牌关键词约束列表，用于限制 LLM 生成卡牌的风格与功能边界


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
