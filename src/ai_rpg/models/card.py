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
    description: str  # 叙事锚点：不含数值，不重述其它字段已确定的效果
    on_play_affixes: List[str] = (
        []
    )  # 即时词缀；格式"[名称]:触发倾向描述"；本卡被打出时结算，仅本次出牌生效；无则 []
    on_hit_affixes: List[str] = (
        []
    )  # 受击词缀；格式"[名称]:触发倾向描述"；持有者被本次出牌命中时触发；无则 []
    on_turn_end_affixes: List[str] = (
        []
    )  # 回合结束词缀；格式"[名称]:触发倾向描述"；持有者每次 pass turn 结算一次，只结算持有者本人手牌中带该词缀的牌；无则 []
    playable: bool = True  # 是否可出牌；False 时系统阻止出牌操作
    exhaust: bool = False  # 出牌后永久归入 ExhaustPile，不进入 DiscardPile 循环
    retain: bool = (
        False  # 回合末保留在手牌（不进入 DiscardPile），跨回合留在 HandComponent
    )
    ethereal: bool = False  # pass turn 时若仍留在手牌，自动移入 ExhaustPileComponent
    transferable: bool = (
        False  # 出牌时从源手牌移除本体，copy 一份到每个解析目标手牌（副本 uuid 重新生成）
    )
    cost: int = 1  # 出牌费用；消耗当前 energy；不足时禁止出牌
    damage: int = 0  # 单次伤害
    hit_count: int = 1  # 攻击次数；>1 时为多段攻击，每段独立结算
    block: int = 0  # 手牌持有期间提供的格挡；出牌仲裁时累加进持有者总防御
    target_type: TargetType = (
        TargetType.SINGLE
    )  # 目标类型，决定目标约束策略；self_target=True 时忽略
    self_target: bool = False  # 锁定自身；True 时目标即出牌者本人，无需 targets
    source: str = ""  # 卡牌来源（生成/注入者）名称；空字符串表示来源未知
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符


###############################################################################################################################################


#######################################################################################################################################
BUILD_CARD_FIELD_DESCRIPTION: Final[
    str
] = f"""每个字段只表达自己的职责，不重复、不互相替代。

## 词缀（三个触发时机）

词缀为自由文本，格式 `[名称]:触发倾向描述`：`名称` 是词缀名，`触发倾向描述` 是该词缀在对应触发时机内的结算倾向。

- `on_play_affixes`：本卡被打出时结算，仅本次出牌生效。
- `on_hit_affixes`：本卡的持有者被本次出牌命中时触发。
- `on_turn_end_affixes`：持有者每次 pass turn 结算一次，只结算持有者本人手牌中带该词缀的牌；配合 `retain` 可跨回合持续触发。

## 功能字段

| 字段 | 说明 |
| --- | --- |
| `playable` | 是否可出牌；false 时系统阻止出牌；默认 true |
| `exhaust` | 出牌后永久消耗，不进弃牌循环；默认 false |
| `retain` | 回合末保留在手牌，不进弃牌堆；默认 false |
| `ethereal` | pass turn 时若仍在手牌则自动消耗；默认 false |
| `transferable` | 出牌时从源手牌移除本体，并 copy 一份到每个目标手牌；默认 false |
| `cost` | 出牌费用（消耗 energy）；默认 1 |
| `damage` | 单次伤害；默认 0 |
| `hit_count` | 攻击次数，多段各自独立结算；默认 1 |
| `block` | 手牌持有期间提供的格挡；默认 0 |
| `self_target` | 锁定出牌者自身；true 时无需 targets |
| `target_type` | 目标类型（见下表）；`self_target=true` 时忽略 |

## 目标类型（target_type）

| 值 | 含义 |
| --- | --- |
| `{TargetType.SINGLE}` | 单个存活角色（默认） |
| `{TargetType.ALL}` | 阵营锚点：以指定目标为锚点，作用于其所在阵营（我方/敌方）的全部存活角色 |
| `{TargetType.SPREAD}` | 阵营锚点：散射锚点所在阵营的存活角色；hit_count 超过人数时每人至少一次，多余随机；否则纯随机 |

## source（系统填充，词缀可引用）

卡牌来源（生成/注入者）名称，由系统填充，无需输出。词缀可引用 `source`：当持有者不等于 `source` 时，用「非 source 者」指代当前持有者。`transferable` 的副本保留原 `source`。"""
