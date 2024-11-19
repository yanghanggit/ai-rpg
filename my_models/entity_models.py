from typing import List, TypedDict
from pydantic import BaseModel
from enum import IntEnum, unique


@unique
class Attributes(IntEnum):
    MAX_HP = 0
    CUR_HP = 1
    DAMAGE = 2
    DEFENSE = 3
    MAX = 20
    BASE_VALUE_SCALE = 100


class PropInstanceModel(BaseModel):
    name: str
    guid: int
    count: int


class ActorInstanceModel(BaseModel):
    name: str
    guid: int
    props: List[PropInstanceModel]
    actor_equipped_props: List[str]


class StageActorInstanceProxy(TypedDict, total=True):
    name: str


class StageInstanceModel(BaseModel):
    name: str
    guid: int
    actors: List[StageActorInstanceProxy]
    spawners: List[str]


class WorldSystemInstanceModel(BaseModel):
    name: str
    guid: int


class ActorModel(BaseModel):
    name: str
    codename: str
    url: str
    kick_off_message: str
    actor_archives: List[str]
    stage_archives: List[str]
    attributes: List[int]
    base_form: str


class StageModel(BaseModel):
    name: str
    codename: str
    stage_profile: str
    url: str
    kick_off_message: str
    stage_graph: List[str]
    attributes: List[int]


class PropModel(BaseModel):
    name: str
    codename: str
    details: str
    type: str
    attributes: List[int]
    appearance: str


class WorldSystemModel(BaseModel):
    name: str
    codename: str
    url: str


class SpawnerModel(BaseModel):
    name: str
    actor_prototypes: List[str]


class DataBaseModel(BaseModel):
    actors: List[ActorModel]
    stages: List[StageModel]
    props: List[PropModel]
    world_systems: List[WorldSystemModel]
    spawners: List[SpawnerModel]


class GameModel(BaseModel):
    save_round: int = 0
    players: List[ActorInstanceModel]
    actors: List[ActorInstanceModel]
    stages: List[StageInstanceModel]
    world_systems: List[WorldSystemInstanceModel]
    database: DataBaseModel
    epoch_script: str
    version: str
