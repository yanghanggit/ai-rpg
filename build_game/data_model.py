from typing import List, Dict, List, Any
from pydantic import BaseModel
from enum import Enum


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


class DataBaseSystemModel(BaseModel):
    actors: List[ActorModel]
    stages: List[StageModel]
    props: List[PropModel]
    world_systems: List[WorldSystemModel]


class PropProxyModel(BaseModel):
    name: str
    count: int


class ActorProxyModel(BaseModel):
    name: str
    props: List[PropProxyModel]
    actor_current_using_prop: List[str]


class StageProxyModel(BaseModel):
    name: str
    props: List[PropProxyModel]
    actors: List[Dict[str, Any]]


class WorldSystemProxyModel(BaseModel):
    name: str


class GameBuilderModel(BaseModel):
    players: List[ActorProxyModel]
    actors: List[ActorProxyModel]
    stages: List[StageProxyModel]
    world_systems: List[WorldSystemProxyModel]
    database: DataBaseSystemModel
    about_game: str
    version: str


class AttributesIndex(Enum):
    MAX_HP = 0
    CUR_HP = 1
    ATTACK = 2
    DEFENSE = 3
    MAX = 10
