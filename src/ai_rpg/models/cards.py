"""卡牌与状态效果模型定义

包含战斗中使用的状态效果（StatusEffect）与卡牌（Card）相关核心模型：
EffectPhase、StatusEffect、Card、DiceValue、Keyword
"""

from enum import IntEnum, StrEnum, unique
from typing import List, final
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator
from .target_type import TargetType


###############################################################################################################################################
@final
@unique
class EffectPhase(StrEnum):
    """状态效果生效阶段

    标记一个状态效果应在战斗流程的哪个阶段起效。

    - draw        : 抽牌阶段（DrawCardsActionSystem）——影响本回合卡牌生成，如"混乱"使牌质下降
    - arbitration : 仲裁阶段（PlayCardsArbitrationSystem）——作为注入仲裁 LLM 的上下文参数，
                    LLM 自由解读其对出牌结算过程的影响（伤害/防御修正、反伤、眩晕等），与出牌绑定
    - round_end   : 回合末阶段（CombatRoundCleanupSystem）——每回合末自动 tick，
                    实体自身 LLM 推理 HP 变化（DOT 如中毒/燃烧持续扣血，HOT 如再生持续回血）
    """

    DRAW = "draw"
    ARBITRATION = "arbitration"
    ROUND_END = "round_end"


###############################################################################################################################################
@final
class StatusEffect(BaseModel):
    """状态效果（增益/减益）

    字段说明：
    - name: 状态效果名称
    - description: 效果描述（静态规则说明，创建后不再修改；如"前3次受击伤害变为1"）
    - duration: 持续回合数；-1 = 永久不过期，>0 = 剩余回合，每回合结束后 -=1，降至 <=0 时移除
    - phase: 生效阶段；决定本效果在哪个战斗阶段被系统读取并应用
    - counter: 特殊计数器；仅 ARBITRATION 阶段效果使用；由仲裁 LLM 按事件更新，不随回合递减
    """

    name: str
    description: (
        str  # 效果描述（静态规则说明，不随状态变化，由 LLM 创建时写入后不再修改）
    )
    duration: int = 3  # 持续回合数；-1=永久，>0=剩余回合
    phase: EffectPhase = EffectPhase.ARBITRATION  # 生效阶段，默认仲裁阶段
    counter: int = (
        0  # 特殊计数器；仅 ARBITRATION 阶段效果使用；由仲裁 LLM 按游戏事件更新（倒计型从初始值递减，累加型从 0 递增）；普通效果保持 0
    )
    source: str = ""  # 效果施加者名称；空字符串表示来源未知
    speed: int = (
        0  # 速度加成（正值加速、负值减速）；叠加到角色最终速度，影响每回合出手顺序
    )
    defense: int = (
        0  # 防御加成（正值增防、负值破甲）；叠加到角色最终防御，影响仲裁阶段的伤害减免
    )
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符

    @field_validator("speed")
    @classmethod
    def clamp_speed(cls, v: int) -> int:
        """将 speed 归一化到 {-1, 0, +1}，保留正负号。"""
        if v > 0:
            return 1
        if v < 0:
            return -1
        return 0


###############################################################################################################################################
@final
class Card(BaseModel):
    """战斗卡牌"""

    name: str
    description: str  # 直接战斗行为描述（第三人称客观描述，说明这张牌造成的即时效果，如伤害；与出牌场景无关）
    affixes: List[str] = (
        []
    )  # 延迟词缀列表；格式"[名称]:触发倾向描述"（如"[燃烧]:可能引发持续扣血"）；出牌后独立推理生成 StatusEffect；无持续效果时输出 []
    modifiers: List[str] = (
        []
    )  # 即时修正词缀列表；格式"[名称]:即时修正描述"（如"[穿甲]:无视目标防御"）；直接注入本次仲裁计算；无即时修正时输出 []
    playable: bool = True  # 是否可出牌；False 时系统阻止出牌操作
    exhaust: bool = (
        False  # 是否为消耗牌；True 时出牌后永久归入 ExhaustPile，不进入 DiscardPile 循环
    )
    damage_dealt: int = 0  # 造成的伤害值（单次）
    hit_count: int = 1  # 攻击次数（默认 1；>1 时为多段攻击，每段独立结算）
    target_type: TargetType = TargetType.ENEMY_SINGLE  # 出牌目标类型，决定目标约束策略
    source: str = ""  # 卡牌来源（生成/注入者名称）；空字符串表示来源未知
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符


###############################################################################################################################################
@final
@unique
class DiceValue(IntEnum):
    """骰值范围常量（0-100 均匀随机整数）"""

    MIN = 0
    MAX = 100


###############################################################################################################################################
@final
class Keyword(BaseModel):
    """卡牌关键词，定义角色生成卡牌时遵循的风格与功能约束。

    通过自然语言描述约束规则，LLM 在生成卡牌时据此限制生成边界。
    空列表表示无约束，角色可自由生成任意风格的卡牌。

    Attributes:
        description: 约束规则的自然语言描述
    """

    description: str


###############################################################################################################################################
