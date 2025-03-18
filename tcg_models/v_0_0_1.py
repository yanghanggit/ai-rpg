from typing import Final, List, Dict, Any, Union, final
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
@final
class ActorPrototype(BaseModel):
    name: str
    code_name: str
    system_message: str
    appearance: str
    type: Union[ActorType, str]


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
# 力量（Strength）
# 敏捷（Dexterity）
# 智慧（Wisdom）
# HP                = 50 + (10 × STR)
# Physical Attack   = 5  + (2  × STR)
# Physical Defense  = 5  + (1  × STR)
# Magic Attack      = 5  + (2  × WIS)
# Magic Defense     = 5  + (1  × WIS)
# Accuracy          = 5  + (2  × DEX)
# Evasion           = 5  + (1  × DEX)
###############################################################################################################################################
@final
class CombatAttributes(BaseModel):
    max_hp: int
    physical_attack: int
    physical_defense: int
    magic_attack: int
    magic_defense: int


###############################################################################################################################################
@final
class BaseAttributes(BaseModel):
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

    @property
    def combat_attrs(self) -> CombatAttributes:
        return CombatAttributes(
            max_hp=self.max_hp,
            physical_attack=self.physical_attack,
            physical_defense=self.physical_defense,
            magic_attack=self.magic_attack,
            magic_defense=self.magic_defense,
        )


###############################################################################################################################################
@final
class ActorInstance(BaseModel):
    name: str
    prototype: str
    guid: int
    kick_off_message: str
    base_attributes: BaseAttributes
    level: int = 1
    hp: int = 0


###############################################################################################################################################
@final
class StageInstance(BaseModel):
    name: str
    prototype: str
    guid: int
    actors: List[str]
    kick_off_message: str


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


@final
class Skill(BaseModel):
    name: str
    description: str
    effect: str


###############################################################################################################################################


@final
class Effect(BaseModel):
    description: str
    round: int
