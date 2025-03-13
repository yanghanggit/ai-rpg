from typing import Final, List, Dict, Any, Optional, Union, final
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


# class ItemObject(BaseModel):
#     name: str
#     guid: int
#     code_name: str
#     count: int = 1
#     value: List[int]


###############################################################################################################################################
# @unique
# class ItemAttributes(IntEnum):
#     MAX_HP = 0
#     CUR_HP = 1
#     MAX = 20


# @final
# class CardObject(ItemObject):  # 可能以后改成ItemObject，类型选card，现阶段先这样 TODO
#     level: int = 1
#     description: str
#     insight: str
#     owner: str  # 测试用的属性，以后用管理系统的方法 TODO

#     # 测试的属性
#     @property
#     def max_hp(self) -> int:
#         if len(self.value) < ItemAttributes.MAX:
#             return self.value[ItemAttributes.MAX_HP]
#         return 0


###############################################################################################################################################
# # TODO 不确定是否保留
# @final
# class TagInfo(BaseModel):
#     name: str
#     description: str


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
class DataBase(BaseModel):
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
    """
    HitInfo类表示将执行的技能效果信息。
    """

    skill: Optional[SkillInfo]
    source: str
    target: str
    value: int
    type: Union[HitType, str]
    dmgtype: DamageType
    buff: Optional[Buff]  # 要添加或者移除的buff
    log: str  # 写在战斗历史里的log，比如A对B用了X技能，造成Y伤害
    text: str  # 角色执行这个动作时想说的话，执行的时候需要广播或者notify出去
    is_cost: bool  # 是否消耗行动力
    is_event: bool  # 是否是事件

    @classmethod
    def get_description(cls) -> str:
        description = f"{cls.__doc__}\n\nAttributes:\n"
        for field_name, field in cls.model_fields.items():
            description += f"- {field_name}: {field.description}\n"
        return description


HitInfo.model_fields["skill"].description = (
    "SkillInfo类实例，代表造成本次Hit的技能信息。类型为SkillInfo。当Hit由事件系统生成时设为None。"
)
HitInfo.model_fields["source"].description = "发起Hit的来源的全名。类型为str。"
HitInfo.model_fields["target"].description = "受Hit影响的目标角色的全名。类型为str。"
HitInfo.model_fields["value"].description = (
    "Hit的数值。类型为int。当type为AddBuff或RemoveBuff时，value为buff的持续时间，当type为Damage或Heal时，value为造成的伤害或治疗量。"
)
HitInfo.model_fields["type"].description = (
    "Hit的类型，类型为HitType枚举，其值包含：AddBuff, RemoveBuff, Damage, Heal。分别代表本次Hit是添加buff，移除buff，造成伤害，治疗。"
)
HitInfo.model_fields["dmgtype"].description = (
    "Hit的伤害类型，类型为DamageType枚举，其值包含：Physical, Magic, Fire, Ice, Heal, Buff。分别代表本次Hit的伤害类型是物理，魔法，火焰，冰霜，治疗，添加或移除buff。"
)
HitInfo.model_fields["buff"].description = (
    "Hit中涉及的buff。类型为Buff类。当type为AddBuff或RemoveBuff时，buff为要添加或移除的buff，当type为Damage或Heal时，buff为None。"
)
HitInfo.model_fields["log"].description = "Hit的描述，用于记录在战斗历史，若技能有数值，需要记录数值。类型为str。"
HitInfo.model_fields["text"].description = (
    "角色执行这个动作时想说的话。类型为str。当Hit由事件系统生成时设为空字符串。"
)
HitInfo.model_fields["is_cost"].description = "是否消耗执行者的行动力。类型为bool。只要角色执行了行动就应设为True，当一个行动被拆解为多个HitInfo时，将其中一个设置为True，其他为False即可。"
HitInfo.model_fields["is_event"].description = (
    "是否是事件。类型为bool。当Hit由事件系统生成时设为True。"
)


class BattleHistory(BaseModel):
    logs: Dict[int, List[str]] = {}


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
