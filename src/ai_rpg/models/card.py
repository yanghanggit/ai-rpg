"""卡牌与状态效果模型定义"""

from typing import Final, List, final
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
        False  # 是否可传递：出牌时从源手牌移除本体，并 copy 一份到每个解析目标的手牌（副本 uuid 重新生成）
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


###############################################################################################################################################


#######################################################################################################################################
BUILD_CARD_FIELD_DESCRIPTION: Final[
    str
] = f"""## 战斗回合流程

战斗按回合推进，每回合依次为：抽牌 → 出牌 → 出牌仲裁 → 过牌 → 回合结束。

- 抽牌：从抽牌堆抽牌入手牌。
- 出牌：发起方消耗 energy 打出一张手牌，指定目标方（或锁定自身）。
- 出牌仲裁：以这张牌的确定性基数（damage / hit_count / block / target_type）结算发起方与目标方（受击方）的 HP 变化。
- 过牌（pass turn）：结束本回合行动。
- 回合结束：所有存活角色都过牌后本轮结束；清理手牌（retain 保留，其余进弃牌堆）。

## 词缀

词缀文本格式：`[名称]:触发倾向描述`（如 `[穿透]:本次伤害无视目标防御`）。词缀只写本次结算内的即时效果；状态、层数、跨回合持续效果不属于词缀（由 transferable / retain 等字段承载）。

- 出牌仲裁：
    - on_play_affixes：发起方打出的这张牌，即时结算，仅本次出牌生效。
    - on_hit_affixes：目标方（受击方）手牌中带该词缀的牌，被命中时触发。
    - 二者是发起方与目标方在出牌仲裁中的互动体现。
- 过牌（pass turn）：
    - on_turn_end_affixes：持有期间由持有者本人结算。

## 卡牌字段说明

每个字段只表达自己的职责，不重复、不互相替代。

| 字段 | 说明 |
| --- | --- |
| name | ≤8 字，体现核心意象 |
| description | 叙事锚点：不含数值，不重述其它字段已确定的效果 |
| cost | 出牌费用（消耗 energy）；默认 1 |
| damage | 单次伤害；默认 0 |
| hit_count | 攻击次数（多段各自独立）；默认 1 |
| block | 持有期格挡；默认 0 |
| target_type | 目标类型（见下表）；self_target=true 时忽略 |
| self_target | 锁定自身；true 时无需 targets |
| on_play_affixes | 见上文 |
| on_hit_affixes | 见上文 |
| on_turn_end_affixes | 见上文 |
| playable | 是否可出牌；默认 true |
| exhaust | 出牌后永久消耗，不进弃牌循环；默认 false |
| retain | 回合末保留在手牌，不进弃牌堆；默认 false |
| ethereal | pass turn 时若仍在手牌则自动消耗；默认 false |
| transferable | 出牌时 copy 一份到每个目标方手牌，并从源手牌移除本体；默认 false |

| target_type | 含义 |
| --- | --- |
| `{TargetType.SINGLE}` | 单个存活角色（默认） |
| `{TargetType.ALL}` | 阵营锚点，作用于该阵营全部存活角色 |
| `{TargetType.SPREAD}` | 阵营锚点，散射该阵营存活角色；hit_count 超过人数时每人至少一次，多余随机；否则纯随机 |"""
