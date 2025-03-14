from typing import Final, List, Dict, Any, Union, final
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from enum import StrEnum, unique

# 注意，不允许动！
SCHEMA_VERSION: Final[str] = "0.0.1"


###############################################################################################################################################
@final
class AgentShortTermMemory(BaseModel):
    name: str = ""
    chat_history: List[SystemMessage | HumanMessage | AIMessage] = []


###############################################################################################################################################
@final
class ComponentSnapshot(BaseModel):
    name: str
    data: Dict[str, Any]


###############################################################################################################################################
@final
class EntitySnapshot(BaseModel):
    name: str
    components: List[ComponentSnapshot]


###############################################################################################################################################
@final
@unique
class ActorType(StrEnum):
    NONE = "None"
    HERO = "Hero"
    MONSTER = "Monster"


###############################################################################################################################################
@final
class ActorPrototype(BaseModel):
    name: str
    code_name: str
    system_message: str
    appearance: str
    type: Union[ActorType, str]


###############################################################################################################################################
@final
@unique
class StageType(StrEnum):
    NONE = "None"
    HOME = "Home"
    DUNGEON = "Dungeon"


###############################################################################################################################################
@final
class StagePrototype(BaseModel):
    name: str
    code_name: str
    system_message: str
    type: Union[StageType, str]


###############################################################################################################################################
@final
class WorldSystemPrototype(BaseModel):
    name: str
    code_name: str
    system_message: str


###############################################################################################################################################
@final
class DataBase(BaseModel):
    actors: Dict[str, ActorPrototype] = {}
    stages: Dict[str, StagePrototype] = {}
    world_systems: Dict[str, WorldSystemPrototype] = {}


###############################################################################################################################################
@final
class ActorInstance(BaseModel):
    name: str
    prototype: str
    guid: int
    kick_off_message: str
    attributes: List[int]


###############################################################################################################################################
@final
class StageInstance(BaseModel):
    name: str
    prototype: str
    guid: int
    actors: List[str]
    kick_off_message: str
    attributes: List[int]
    next: List[str]


###############################################################################################################################################
@final
class WorldSystemInstance(BaseModel):
    name: str
    prototype: str
    guid: int
    kick_off_message: str


###############################################################################################################################################
# 生成世界的根文件，就是世界的起点
@final
class Boot(BaseModel):
    name: str = ""
    version: str = ""
    epoch_script: str = ""
    players: List[ActorInstance] = []
    actors: List[ActorInstance] = []
    stages: List[StageInstance] = []
    world_systems: List[WorldSystemInstance] = []
    data_base: DataBase = DataBase()


###############################################################################################################################################
# 生成世界的运行时文件，记录世界的状态
@final
class World(BaseModel):
    version: str = SCHEMA_VERSION
    boot: Boot = Boot()
    entities_snapshot: List[EntitySnapshot] = []
    agents_short_term_memory: Dict[str, AgentShortTermMemory] = {}


###############################################################################################################################################
