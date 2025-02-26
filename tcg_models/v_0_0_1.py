from typing import Final, List, Dict, Any, Union, final
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from rpg_models.event_models import BaseEvent
from enum import IntEnum, StrEnum, unique

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
""" @final
class PropObject(BaseModel):
    name: str
    guid: int
    count: int
    code_name: str
    details: str
    type: str
    appearance: str
    insight: str
    attributes: List[int] """


class ItemObject(BaseModel):
    name: str
    guid: int
    code_name: str
    count: int = 1
    value: List[int]


@unique
class ItemAttributes(IntEnum):
    MAX_HP = 0
    CUR_HP = 1
    MAX = 20


@final
class CardObject(ItemObject):  # 可能以后改成ItemObject，类型选card，现阶段先这样 TODO
    level: int = 1
    holder: str
    performer: str
    description: str
    insight: str
    target: str

    # 测试的属性
    @property
    def max_hp(self) -> int:
        if len(self.value) < ItemAttributes.MAX:
            return self.value[ItemAttributes.MAX_HP]
        return 0


###############################################################################################################################################
@final
class WorldDataBase(BaseModel):
    actors: Dict[str, ActorPrototype] = {}
    stages: Dict[str, StagePrototype] = {}
    # props: Dict[str, PropObject] = {}  # 这里就放这个。
    # cards: Dict[str, CardObject] = {} # 真的需要吗？ 把卡池数据存在actor里就行，后续用item的时候再加上 TODO
    world_systems: Dict[str, WorldSystemPrototype] = {}


###############################################################################################################################################
@final
class ActorInstance(BaseModel):
    name: str
    guid: int
    kick_off_message: str
    card_pool: List[CardObject]  # 感觉这个应该放进Prototype里 TODO
    attributes: List[int]


###############################################################################################################################################
@final
class StageInstance(BaseModel):
    name: str
    guid: int
    actors: List[str]
    kick_off_message: str
    # props: List[PropObject]
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
    version: str = SCHEMA_VERSION
    root: WorldRoot = WorldRoot()
    entities_snapshot: List[EntitySnapshot] = []
    agents_short_term_memory: Dict[str, AgentShortTermMemory] = {}


###############################################################################################################################################
