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
# 序号	职能描述	类名 (英文)	中文直译	核心职责说明
# 1	物理攻击者	Striker	强袭者	专注高物理伤害输出，近战或远程攻击
# 2	物理防御者	Guardian	守护者	吸收物理伤害、保护队友，具备嘲讽/护盾技能
# 3	魔法攻击者	Mage	法师	释放元素/奥术魔法造成范围或单体魔法伤害
# 4	魔法防御者	Warden	结界师	抵抗魔法伤害、解除负面效果、提供魔法抗性增益
# 5	治疗者	Healer	治愈者	恢复队友生命值、驱散减益状态
# 6	强化者	Enhancer	增益师	为队友附加增益效果（攻击/防御/速度提升等）
# 7	弱化者	Debilitator	弱化师	对敌人施加减益效果（降低属性、附加控制等）
# 8	召唤者	Summoner	召唤师	召唤单位（继承上述职能）协同作战

# 方案 1：使用 CombatRole（推荐）
# 名称：CombatRole
# 说明：
#   直译为“战斗角色职能”，明确表达这是战斗中的职责分工。
#   比 Job 更聚焦于战斗场景，避免与职业（如铁匠、商人）混淆。


@final
class CombatRole(BaseModel):
    name: str
    description: str

    @property
    def as_prompt(self) -> str:
        return f"<{self.name}>:{self.description}"


STRIKER: Final[CombatRole] = CombatRole(
    name="强袭者", description="专注高物理伤害输出，近战或远程攻击"
)
GUARDIAN: Final[CombatRole] = CombatRole(
    name="守护者", description="吸收物理伤害、保护队友，具备嘲讽/护盾技能"
)
MAGE: Final[CombatRole] = CombatRole(
    name="法师", description="释放元素/奥术魔法造成范围或单体魔法伤害"
)
WARDEN: Final[CombatRole] = CombatRole(
    name="结界师", description="抵抗魔法伤害、解除负面效果、提供魔法抗性增益"
)
HEALER: Final[CombatRole] = CombatRole(
    name="治愈者", description="恢复队友生命值、驱散减益状态"
)
ENHANCER: Final[CombatRole] = CombatRole(
    name="增益师", description="为队友附加增益效果（攻击/防御/速度提升等）"
)
DEBILITATOR: Final[CombatRole] = CombatRole(
    name="弱化师", description="对敌人施加减益效果（降低属性、附加控制等）"
)
SUMMONER: Final[CombatRole] = CombatRole(
    name="召唤师", description="召唤单位（继承上述职能）协同作战"
)


###############################################################################################################################################
@final
class ActorPrototype(BaseModel):
    name: str
    code_name: str
    base_system_message: str
    appearance: str
    type: str
    combat_roles: List[CombatRole]


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
    guid: int
    system_message: str
    kick_off_message: str
    level: int = 1
    base_attributes: BaseAttributes


###############################################################################################################################################
@final
class StageInstance(BaseModel):
    name: str
    prototype: str
    guid: int
    actors: List[str]
    system_message: str
    kick_off_message: str


###############################################################################################################################################
@final
class WorldSystemInstance(BaseModel):
    name: str
    prototype: str
    guid: int
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


###############################################################################################################################################
