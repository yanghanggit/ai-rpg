from typing import List, Dict, Any, Union, final
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from models.event_models import BaseEvent
from enum import StrEnum


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
class ActorPrototype(BaseModel):
    class ActorType(StrEnum):
        UNDIFINED = "Undefined"
        PLAYER = "Player"
        HERO = "Hero"
        MONSTER = "Monster"
        BOSS = "Boss"

    name: str
    code_name: str
    system_message: str
    appearance: str
    type: Union[ActorType, str]


###############################################################################################################################################
@final
class StagePrototype(BaseModel):
    class StageType(StrEnum):
        UNDIFINED = "Undefined"
        HOME = "Home"
        DUNGEON = "Dungeon"

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
class PropObject(BaseModel):
    name: str
    guid: int
    count: int
    code_name: str
    details: str
    type: str
    appearance: str
    insight: str
    attributes: List[int]


###############################################################################################################################################
@final
class WorldDataBase(BaseModel):
    actors: Dict[str, ActorPrototype] = {}
    stages: Dict[str, StagePrototype] = {}
    props: Dict[str, PropObject] = {}  # 这里就放这个。
    world_systems: Dict[str, WorldSystemPrototype] = {}


###############################################################################################################################################
@final
class ActorInstance(BaseModel):
    name: str
    guid: int
    kick_off_message: str
    props: List[PropObject]
    attributes: List[int]


###############################################################################################################################################
@final
class StageInstance(BaseModel):
    name: str
    guid: int
    actors: List[str]
    kick_off_message: str
    props: List[PropObject]
    attributes: List[int]
    next: List[str]


###############################################################################################################################################
@final
class WorldSystemInstance(BaseModel):
    name: str
    guid: int
    kick_off_message: str


###############################################################################################################################################
# 生成世界的根文件，就是世界的起点
@final
class WorldRoot(BaseModel):
    name: str = ""
    version: str = ""
    epoch_script: str = ""
    players: List[ActorInstance] = []
    actors: List[ActorInstance] = []
    stages: List[StageInstance] = []
    world_systems: List[WorldSystemInstance] = []
    data_base: WorldDataBase = WorldDataBase()


###############################################################################################################################################
# 生成世界的运行时文件，记录世界的状态
@final
class WorldRuntime(BaseModel):
    root: WorldRoot = WorldRoot()
    entities_snapshot: List[EntitySnapshot] = []
    agents_short_term_memory: Dict[str, AgentShortTermMemory] = {}


###############################################################################################################################################


# 玩家客户端消息
class PlayerNotification(BaseModel):
    tag: str
    sender: str
    index: int = 0
    agent_event: BaseEvent  # 要根部的类，其实只需要它的序列化能力，其余的不要，所以不要出现具体类型的调用！
