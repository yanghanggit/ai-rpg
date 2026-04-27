"""战斗相关模型定义

包含战斗状态、战斗结果、状态效果、卡牌、战斗回合与战斗实例等核心模型。
"""

from enum import IntEnum, StrEnum, unique
from typing import List, Optional, final
from pydantic import BaseModel, Field


###############################################################################################################################################
# 战斗状态枚举
@final
@unique
class CombatState(IntEnum):
    NONE = 0  # 无状态
    INITIALIZATION = 1  # 初始化，需要同步一些数据与状态
    ONGOING = 2  # 运行中，不断进行战斗推理
    COMPLETE = 3  # 结束，需要进行结算
    POST_COMBAT = 4  # 战斗等待进入新一轮战斗或者回家


###############################################################################################################################################
# 表示战斗的状态
@final
@unique
class CombatResult(IntEnum):
    NONE = 0  # 无结果
    WIN = 1  # 胜利
    LOSE = 2  # 失败


###############################################################################################################################################
@final
@unique
class StatusEffectPhase(StrEnum):
    """状态效果生效阶段

    标记一个状态效果应在战斗流程的哪个阶段起效。

    - draw        : 抽牌阶段（DrawCardsActionSystem）——影响本回合卡牌生成，如"混乱"使牌质下降
    - play        : 出牌阶段（PlayCardsActionSystem）——影响出牌行为，如"束缚"禁止出攻击牌
    - arbitration : 仲裁阶段（ArbitrationActionSystem）——影响伤害/格挡结算，如"虚弱"伤害−2、"坚甲"格挡+3
    """

    DRAW = "draw"
    PLAY = "play"
    ARBITRATION = "arbitration"


###############################################################################################################################################
@final
class StatusEffect(BaseModel):
    """状态效果（增益/减益）

    字段说明：
    - name: 状态效果名称
    - description: 效果描述（含表现与数值影响，如"我感到手臂刺痛，攻击力−2"）
    - duration: 持续回合数；-1 = 永久不过期，>0 = 剩余回合，每回合结束后 -=1，降至 <=0 时移除
    - phase: 生效阶段；决定本效果在哪个战斗阶段被系统读取并应用
    """

    name: str
    description: str  # 效果描述（含表现与数值影响）
    duration: int = 3  # 持续回合数；-1=永久，>0=剩余回合
    phase: StatusEffectPhase = StatusEffectPhase.ARBITRATION  # 生效阶段，默认仲裁阶段
    source: str = ""  # 效果施加者名称；空字符串表示来源未知


###############################################################################################################################################
@final
@unique
class CardTargetType(StrEnum):
    """卡牌目标类型

    声明一张卡牌的打击范围，由 LLM 在抽卡时输出，出牌阶段系统据此做目标验证或自动填充。

    当前约束策略：
    - enemy_single：targets 必须恰好包含 1 名存活敌方角色名
    - enemy_all：targets 由系统自动替换为场上全部存活敌方，调用方传入值被忽略
    - enemy_random_multi：targets 由系统预先随机生成，长度 = hit_count，每段独立随机命中一名存活敌方
                          （允许重复命中同一目标）；仲裁系统按段分配结算，参考《杀戮尖塔》飞剑回旋镖
    - ally_single / ally_all：暂不约束，targets 由调用方自由传入（占位，后续扩展）
    - self_only：targets 由系统自动替换为施法者自身，调用方传入值被忽略；
                 典型用途：纯防御（提升格挡）、呼吸法（自我恢复）、强化自身 buff 等
                 与 ally_single 的区别：ally_single 可指向任意存活友方，self_only 严格限定为施法者本人
    """

    ENEMY_SINGLE = "enemy_single"
    ENEMY_ALL = "enemy_all"
    ENEMY_RANDOM_MULTI = "enemy_random_multi"
    ALLY_SINGLE = "ally_single"
    ALLY_ALL = "ally_all"
    SELF_ONLY = "self_only"


###############################################################################################################################################
@final
class Card(BaseModel):
    """战斗卡牌"""

    name: str
    description: str  # 直接战斗行为描述（第三人称客观描述，说明这张牌造成的即时效果，如伤害/格挡；与出牌场景无关）
    effects: List[str] = (
        []
    )  # 词缀列表，每项为"[名称]:短句描述"格式（如"[燃烧]:可能引发持续火焰伤害"）；为空时仲裁后不触发 AddStatusEffectsAction LLM 推理
    damage_dealt: int = 0  # 造成的伤害值（单次）
    block_gain: int = 0  # 提供的格挡增量
    hit_count: int = (
        1  # 攻击次数（默认 1；>1 时为多段攻击，每段各自抵挡格挡后依次结算）
    )
    target_type: CardTargetType = (
        CardTargetType.ENEMY_SINGLE
    )  # 出牌目标类型，决定目标约束策略
    source: str = ""  # 卡牌来源（生成/注入者名称）；空字符串表示来源未知


###############################################################################################################################################
@final
class Round(BaseModel):
    """战斗回合"""

    completed_actors: List[str] = []  # 已完成出牌的角色名称（按出手顺序追加，允许重复）
    actor_order_snapshots: List[List[str]] = Field(
        default_factory=list
    )  # 每次回合开始时的有行动力角色快照（去重、按优先级排列）；由 CombatRoundTransitionSystem 写入
    current_turn_actor_name: Optional[str] = (
        None  # 当前 turn 应行动的角色名；由系统写入，供 TUI 等无 ECS 访问的消费点读取
    )
    is_completed: bool = False  # 回合结束标记；由 CombatRoundCompletionSystem 写入
    combat_log: List[str] = []  # 战斗计算日志，每次出手追加一条
    narrative: List[str] = []  # 叙事文本/演出描述，每次出手追加一条


###############################################################################################################################################
@final
class Combat(BaseModel):
    """战斗实例"""

    name: str
    state: CombatState = CombatState.NONE
    result: CombatResult = CombatResult.NONE
    rounds: List[Round] = []
    retreated: bool = False  # 是否通过撤退结束本次战斗


###############################################################################################################################################
