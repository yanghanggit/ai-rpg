"""卡牌与状态效果模型定义

包含战斗中使用的状态效果（StatusEffect）与卡牌（Card）相关核心模型：
CombatPhase、StatusEffect、Card、DiceValue、Keyword
"""

from typing import List, Optional, final
from uuid import uuid4
from pydantic import BaseModel, Field
from .target_type import TargetType


###############################################################################################################################################
@final
class Card(BaseModel):
    """战斗卡牌"""

    name: str
    description: str  # 直接战斗行为描述（第三人称客观描述，说明这张牌造成的即时效果，如伤害；与出牌场景无关）
    on_play_affixes: List[str] = (
        []
    )  # 即时词缀列表；格式"[名称]:触发倾向描述"（如"[穿透]:本次伤害无视目标防御"）；参与本卡本次出牌仲裁，由仲裁 LLM 直接套用，不落地 StatusEffect；无即时效果时输出 []
    on_hit_affixes: List[str] = (
        []
    )  # 延迟词缀列表；格式"[名称]:触发倾向描述"（如"[燃烧]:可能引发持续扣血"）；出牌命中目标后独立推理生成 StatusEffect；无持续效果时输出 []
    playable: bool = True  # 是否可出牌；False 时系统阻止出牌操作
    exhaust: bool = (
        False  # 是否为消耗牌；True 时出牌后永久归入 ExhaustPile，不进入 DiscardPile 循环
    )
    cost: int = 1  # 出牌费用；消耗行动者当前 energy 的点数；energy 不足时禁止出牌
    damage: int = 0  # 造成的伤害值（单次）
    hit_count: int = 1  # 攻击次数（默认 1；>1 时为多段攻击，每段独立结算）
    target_type: TargetType = TargetType.SINGLE  # 出牌目标类型，决定目标约束策略
    source: str = ""  # 卡牌来源（生成/注入者名称）；空字符串表示来源未知
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符
    original_data: Optional["Card"] = (
        None  # 原始牌快照；None=未被修改过；首次修改时写入，后续修改不覆盖
    )


Card.model_rebuild()  # 解析 original_data 的前向引用


###############################################################################################################################################
