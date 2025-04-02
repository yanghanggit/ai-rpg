from typing import Final, List, Dict, Any, final
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from enum import StrEnum, unique

# 注意，不允许动！
SCHEMA_VERSION: Final[str] = "0.0.1"


###############################################################################################################################################
@final
@unique
class ActorType(StrEnum):
    NONE = "None"
    HERO = "Hero"
    MONSTER = "Monster"


###############################################################################################################################################
@final
@unique
class StageType(StrEnum):
    NONE = "None"
    HOME = "Home"
    DUNGEON = "Dungeon"


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


# 所有道具的基础定义
class Item(BaseModel):
    name: str
    description: str


###############################################################################################################################################
class Card(Item):
    effect: str


###############################################################################################################################################
# 技能是一种特殊的道具，它有一个额外的效果。
@final
class Skill(Card):
    pass


###############################################################################################################################################
# 技能产生的影响。
@final
class StatusEffect(Item):
    rounds: int


###############################################################################################################################################
@final
class ActorPrototype(BaseModel):
    name: str
    code_name: str
    base_system_message: str
    appearance: str
    type: str


###############################################################################################################################################
@final
class StagePrototype(BaseModel):
    name: str
    code_name: str
    base_system_message: str
    type: str


###############################################################################################################################################
@final
class WorldSystemPrototype(BaseModel):
    name: str
    code_name: str
    base_system_message: str


###############################################################################################################################################
@final
class DataBase(BaseModel):
    actors: Dict[str, ActorPrototype] = {}
    stages: Dict[str, StagePrototype] = {}
    world_systems: Dict[str, WorldSystemPrototype] = {}


###############################################################################################################################################
# Max HP            = 50 + (10 × STR)
# Physical Attack   = 5  + (2  × STR)
# Physical Defense  = 5  + (1  × STR)
# Magic Attack      = 5  + (2  × WIS)
# Magic Defense     = 5  + (1  × WIS)
# Accuracy          = 5  + (2  × DEX)
# Evasion           = 5  + (1  × DEX)
###############################################################################################################################################
@final
class BaseAttributes(BaseModel):
    hp: int = 0
    strength: int
    dexterity: int
    wisdom: int

    @property
    def max_hp(self) -> int:
        return 50 + (10 * self.strength)

    @property
    def physical_attack(self) -> int:
        return 5 + (2 * self.strength)

    @property
    def physical_defense(self) -> int:
        return 5 + (1 * self.strength)

    @property
    def magic_attack(self) -> int:
        return 5 + (2 * self.wisdom)

    @property
    def magic_defense(self) -> int:
        return 5 + (1 * self.wisdom)


###############################################################################################################################################
@final
class ActorInstance(BaseModel):
    name: str
    prototype: str
    #guid: int
    system_message: str
    kick_off_message: str
    base_attributes: BaseAttributes


###############################################################################################################################################
@final
class StageInstance(BaseModel):
    name: str
    prototype: str
    #guid: int
    actors: List[str]
    system_message: str
    kick_off_message: str


###############################################################################################################################################
@final
class WorldSystemInstance(BaseModel):
    name: str
    prototype: str
    #guid: int
    system_message: str
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
    runtime_index: int = 1000
    # runtime_players: List[ActorInstance] = []
    # runtime_actors: List[ActorInstance] = []
    # runtime_stages: List[StageInstance] = []
    # runtime_world_systems: List[WorldSystemInstance] = []

    @property
    def data_base(self) -> DataBase:
        return self.boot.data_base

    @property
    def players(self) -> List[ActorInstance]:
        return self.boot.players

    @property
    def actors(self) -> List[ActorInstance]:
        return self.boot.actors

    @property
    def stages(self) -> List[StageInstance]:
        return self.boot.stages

    @property
    def world_systems(self) -> List[WorldSystemInstance]:
        return self.boot.world_systems

    def next_runtime_index(self) -> int:
        self.runtime_index += 1
        return self.runtime_index


###############################################################################################################################################
