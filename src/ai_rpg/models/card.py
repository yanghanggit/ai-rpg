"""卡牌与状态效果模型定义"""

from typing import List, Optional, final
from uuid import uuid4

from pydantic import BaseModel, Field

from .items import GearItem
from .target_type import TargetType


###############################################################################################################################################
@final
class Card(BaseModel):
    """战斗卡牌"""

    name: str
    description: str  # 直接战斗行为描述（第三人称客观描述，说明这张牌造成的即时效果，如伤害；与出牌场景无关）
    on_play_affixes: List[str] = (
        []
    )  # 即时词缀列表；格式"[名称]:触发倾向描述"（如"[穿透]:本次伤害无视目标防御"）；参与本卡本次出牌仲裁，由仲裁 LLM 直接套用；无即时效果时输出 []
    on_hit_affixes: List[str] = (
        []
    )  # 受击词缀列表；格式"[名称]:触发倾向描述"（如"[反伤]:受到攻击时对出牌者造成2点伤害"）；持有在手牌期间生效，当持有者被本次出牌命中时触发；无受击效果时输出 []
    on_turn_end_affixes: List[str] = (
        []
    )  # 回合结束词缀列表；格式"[名称]:触发倾向描述"（如"[灼烧]:回合结束时对持有者造成 damage 点伤害"）；持有在手牌期间生效，回合结束（pass turn）时触发；无则 []
    playable: bool = True  # 是否可出牌；False 时系统阻止出牌操作
    exhaust: bool = (
        False  # 是否为消耗牌；True 时出牌后永久归入 ExhaustPile，不进入 DiscardPile 循环
    )
    retain: bool = (
        False  # 是否保留在手牌中；True 时回合末不清入手牌（不进入 DiscardPile），跨回合留在 HandComponent
    )
    ethereal: bool = (
        False  # 虚无词缀；True 时 pass turn 时若仍留在手牌中，自动移入 ExhaustPileComponent
    )
    transferable: bool = (
        False  # 是否可传递：出牌时 copy 一份到每个解析目标的手牌（source 保持原卡，uuid 重新生成）
    )
    cost: int = 1  # 出牌费用；消耗行动者当前 energy 的点数；energy 不足时禁止出牌
    damage: int = 0  # 造成的伤害值（单次）
    hit_count: int = 1  # 攻击次数（默认 1；>1 时为多段攻击，每段独立结算）
    block: int = 0  # 手牌持有期间提供的格挡值；出牌仲裁时累加进持有者总防御
    target_type: TargetType = (
        TargetType.SINGLE
    )  # 出牌目标类型，决定目标约束策略；self_target=True 时忽略
    self_target: bool = False  # 出牌是否锁定自身；True 时目标即出牌者本人，无需 targets
    source: str = ""  # 卡牌来源（生成/注入者名称）；空字符串表示来源未知
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符
    gear_item: Optional[GearItem] = (
        None  # 由 GearItem 临时转化而来的卡牌时，存储来源 GearItem；普通卡牌为 None
    )


###############################################################################################################################################
