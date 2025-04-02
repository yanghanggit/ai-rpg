from typing import Final, List, Dict, Any, final
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from enum import IntEnum, StrEnum, unique

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
# 表示战斗的状态 Phase
@final
@unique
class CombatPhase(IntEnum):
    NONE = (0,)
    KICK_OFF = (1,)  # 初始化，需要同步一些数据与状态
    ONGOING = (2,)  # 运行中，不断进行战斗推理
    COMPLETE = 3  # 结束，需要进行结算
    POST_WAIT = 4  # 战斗等待进入新一轮战斗或者回家


###############################################################################################################################################
# 表示战斗的状态
@final
@unique
class CombatResult(IntEnum):
    NONE = (0,)
    HERO_WIN = (1,)  # 胜利
    HERO_LOSE = (2,)  # 失败


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
# 技能产生的影响。
@final
class StatusEffect(Item):
    rounds: int


###############################################################################################################################################
class Card(Item):
    effect: str


###############################################################################################################################################
# 技能是一种特殊的道具，它有一个额外的效果。
@final
class Skill(Card):
    pass


###############################################################################################################################################
# 表示一个回合
class Round(BaseModel):
    tag: str
    round_turns: List[str] = []
    select_report: Dict[str, str] = {}
    stage_director_calculation: str = ""
    stage_director_performance: str = ""
    feedback_report: Dict[str, str] = {}


###############################################################################################################################################
# 表示一个战斗
class Combat(BaseModel):

    name: str
    phase: CombatPhase = CombatPhase.NONE
    result: CombatResult = CombatResult.NONE
    rounds: List[Round] = []
    summarize_report: Dict[str, str] = {}


###############################################################################################################################################
class Engagement(BaseModel):
    combats: List[Combat] = []


###############################################################################################################################################
@final
class ActorPrototype(BaseModel):
    name: str
    type: str
    profile: str
    appearance: str


###############################################################################################################################################
@final
class StagePrototype(BaseModel):
    name: str
    type: str
    profile: str


###############################################################################################################################################
@final
class DataBase(BaseModel):
    actors: Dict[str, ActorPrototype] = {}
    stages: Dict[str, StagePrototype] = {}


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
class Actor(BaseModel):
    name: str
    prototype: ActorPrototype
    system_message: str
    kick_off_message: str
    base_attributes: BaseAttributes


###############################################################################################################################################
@final
class Stage(BaseModel):
    name: str
    prototype: StagePrototype
    system_message: str
    kick_off_message: str
    actors: List[Actor]


###############################################################################################################################################
@final
class WorldSystem(BaseModel):
    name: str
    system_message: str
    kick_off_message: str


###############################################################################################################################################
# TODO临时的，先管理下。
class Dungeon(BaseModel):
    name: str
    levels: List[Stage]
    engagement: Engagement
    position: int = 0

    @property
    def actors(self) -> List[Actor]:
        return [actor for stage in self.levels for actor in stage.actors]


###############################################################################################################################################
# 生成世界的根文件，就是世界的起点
@final
class Boot(BaseModel):
    name: str = ""
    epoch_script: str = ""
    stages: List[Stage] = []
    world_systems: List[WorldSystem] = []
    data_base: DataBase = DataBase()

    @property
    def actors(self) -> List[Actor]:
        return [actor for stage in self.stages for actor in stage.actors]


###############################################################################################################################################
# 生成世界的运行时文件，记录世界的状态
@final
class World(BaseModel):
    version: str = SCHEMA_VERSION
    runtime_index: int = 1000
    entities_snapshot: List[EntitySnapshot] = []
    agents_short_term_memory: Dict[str, AgentShortTermMemory] = {}
    dungeon: Dungeon = Dungeon(name="", levels=[], engagement=Engagement())
    boot: Boot = Boot()

    @property
    def data_base(self) -> DataBase:
        return self.boot.data_base

    def next_runtime_index(self) -> int:
        self.runtime_index += 1
        return self.runtime_index


###############################################################################################################################################
