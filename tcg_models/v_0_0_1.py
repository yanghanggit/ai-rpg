from typing import Final, List, Dict, Any, Optional, Union, final
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
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


class ItemObject(BaseModel):
    name: str
    guid: int
    code_name: str
    count: int = 1
    value: List[int]


###############################################################################################################################################
@unique
class ItemAttributes(IntEnum):
    MAX_HP = 0
    CUR_HP = 1
    MAX = 20


@final
class CardObject(ItemObject):  # 可能以后改成ItemObject，类型选card，现阶段先这样 TODO
    level: int = 1
    description: str
    insight: str
    owner: str  # 测试用的属性，以后用管理系统的方法 TODO

    # 测试的属性
    @property
    def max_hp(self) -> int:
        if len(self.value) < ItemAttributes.MAX:
            return self.value[ItemAttributes.MAX_HP]
        return 0


###############################################################################################################################################
# TODO 不确定是否保留
@final
class TagInfo(BaseModel):
    name: str
    description: str


###############################################################################################################################################
# TODO，这个框里的全是临时的，没细想，能跑就行，等重构
class TriggerType(StrEnum):
    NONE = "None"
    TURN_START = "TurnStart"
    ON_ATTACKED = "OnAttacked"
    ON_PLANNING = "OnPlanning"


class Buff(BaseModel):
    name: str
    description: str
    timing: TriggerType
    is_debuff: bool


###############################################################################################################################################
@final
class WorldDataBase(BaseModel):
    actors: Dict[str, ActorPrototype] = {}
    stages: Dict[str, StagePrototype] = {}
    world_systems: Dict[str, WorldSystemPrototype] = {}
    buffs: Dict[str, Buff] = {}


class SkillInfo(BaseModel):
    name: str
    description: str
    values: List[float]
    buff: Optional[Buff]


class ActiveSkill(SkillInfo):
    pass


class TriggerSkill(SkillInfo):
    timing: TriggerType
    pass


class HitType(StrEnum):
    NONE = "None"
    ADDBUFF = "AddBuff"
    REMOVEBUFF = "RemoveBuff"
    DAMAGE = "Damage"
    HEAL = "Heal"


class DamageType(StrEnum):
    PHYSICAL = "Physical"
    MAGIC = "Magic"
    FIRE = "Fire"
    ICE = "Ice"
    HEAL = "Heal"
    BUFF = "Buff"


class HitInfo(BaseModel):
    skill: SkillInfo
    source: str
    target: str
    value: int
    type: HitType
    dmgtype: DamageType
    buff: Optional[Buff]  # 要添加或者移除的buff
    log: str  # 写在战斗历史里的log，比如A对B用了X技能，造成Y伤害
    text: str  # 角色执行这个动作时想说的话，执行的时候需要广播或者notify出去
    is_cost: bool  # 是否消耗行动力


class EventMsg(BaseModel):
    event: str
    option: int
    result: str


class BattleHistory(BaseModel):
    logs: Dict[int, List[str]]


###############################################################################################################################################
@final
class ActorInstance(BaseModel):
    name: str
    guid: int
    kick_off_message: str
    active_skills: List[ActiveSkill]
    trigger_skills: List[TriggerSkill]
    buffs: Dict[str, int]
    attributes: List[int]  # HP/MaxHP/ActionTimes/MaxActionTimes/STR/AGI/WIS
    # tags: List[TagInfo]


###############################################################################################################################################
@final
class StageInstance(BaseModel):
    name: str
    guid: int
    actors: List[str]
    kick_off_message: str
    attributes: List[int]
    next: List[str]
    # tags: List[TagInfo]


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
