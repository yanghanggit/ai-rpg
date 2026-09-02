from enum import StrEnum, unique
from typing import List, final, Optional
from pydantic import BaseModel
from .serialization import ComponentSerialization
from .character_stats import CharacterStats
from .card import Card
from .items import CostumeItem


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
    custom_item: Optional[CostumeItem] = None  # 当前穿戴的时装，None 表示未穿戴任何时装
    # #keywords: List[str] = (
    #     []
    # )  # 卡牌关键词约束列表，用于限制 LLM 生成卡牌的功能边界（规则层）；叙事主题由角色设定（profile）提炼
    cards: List[Card] = []  # 预置卡牌列表


###############################################################################################################################################
@final
class Stage(BaseModel):
    name: str
    type: StageType
    profile: str
    system_message: str
    actors: List[Actor]


###############################################################################################################################################
@final
class World(BaseModel):
    name: str
    system_message: str
    components: List[ComponentSerialization] = []


###############################################################################################################################################
