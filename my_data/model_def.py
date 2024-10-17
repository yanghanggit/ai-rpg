from typing import List, Dict, List, Any
from pydantic import BaseModel
from enum import Enum, StrEnum


class ActorModel(BaseModel):
    name: str
    codename: str
    url: str
    kick_off_message: str
    actor_archives: List[str]
    stage_archives: List[str]
    attributes: List[int]
    body: str


class StageModel(BaseModel):
    name: str
    codename: str
    description: str
    url: str
    kick_off_message: str
    stage_graph: List[str]
    attributes: List[int]


class PropModel(BaseModel):
    name: str
    codename: str
    description: str
    type: str
    attributes: List[int]
    appearance: str


class WorldSystemModel(BaseModel):
    name: str
    codename: str
    url: str


class DataBaseModel(BaseModel):
    actors: List[ActorModel]
    stages: List[StageModel]
    props: List[PropModel]
    world_systems: List[WorldSystemModel]


class PropProxyModel(BaseModel):
    name: str
    guid: int
    count: int


class ActorProxyModel(BaseModel):
    name: str
    guid: int
    props: List[PropProxyModel]
    actor_current_using_prop: List[str]


class StageProxyModel(BaseModel):
    name: str
    guid: int
    props: List[PropProxyModel]
    actors: List[Dict[str, Any]]


class WorldSystemProxyModel(BaseModel):
    name: str
    guid: int


class GameModel(BaseModel):
    players: List[ActorProxyModel]
    actors: List[ActorProxyModel]
    stages: List[StageProxyModel]
    world_systems: List[WorldSystemProxyModel]
    database: DataBaseModel
    about_game: str
    version: str


class AttributesIndex(Enum):
    MAX_HP = 0
    CUR_HP = 1
    DAMAGE = 2
    DEFENSE = 3
    MAX = 10


class PropType(StrEnum):
    TYPE_SPECIAL = "Special"
    TYPE_WEAPON = "Weapon"
    TYPE_CLOTHES = "Clothes"
    TYPE_NON_CONSUMABLE_ITEM = "NonConsumableItem"
    TYPE_CONSUMABLE_ITEM = "ConsumableItem"
    TYPE_SKILL = "Skill"


class ComponentDumpModel(BaseModel):
    name: str
    data: Dict[str, Any]


class EntityDumpModel(BaseModel):
    name: str
    components: List[ComponentDumpModel]
