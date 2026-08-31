"""Card 构造提示词构建器模块"""

from typing import Final
from ..models import TargetType


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

## 词缀（on_play / on_hit / on_turn_end）

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


#######################################################################################################################################
