"""Card 构造提示词构建器模块

集中管理所有用于让 LLM 生成/构造 Card 的提示词构建函数与相关数据结构，
方便统一阅读与修改 Card 的生成规则。
"""

from typing import List
from pydantic import BaseModel
from ..models import CharacterStats, TargetType


#######################################################################################################################################
class DeckCardEntry(BaseModel):
    """单张卡牌条目（用于 DeckGenerateResponse 解析）"""

    name: str
    description: str
    affixes: List[str] = []
    modifiers: List[str] = []
    playable: bool = True
    exhaust: bool = False
    cost: int = 1
    damage_dealt: int
    energy_delta: int = 0
    hit_count: int = 1
    target_type: str = TargetType.ENEMY_SINGLE


#######################################################################################################################################
class DeckGenerateResponse(BaseModel):
    """LLM 一次生成 num_cards 张牌库卡牌的响应模型"""

    cards: List[DeckCardEntry]


#######################################################################################################################################
def build_card_field_description() -> str:
    """返回 Card 完整字段说明 Markdown 块（字段表格 + TargetType 表格）。

    供各提示词构建函数统一引用，避免重复维护。
    """
    return f"""## 卡牌字段说明

| 字段 | 说明 |
|---|---|
| name | 卡牌名称（≤8字），富有想象力，体现行动意图 |
| description | 第三人称，客观描述卡牌对应的战斗行为（不含数值，不重述数值字段已确定的效果） |
| affixes | 延迟词缀列表，格式 `[名称]:触发倾向描述`；出牌后独立推理生成持续状态效果；无则 [] |
| modifiers | 即时修正词缀列表，格式 `[名称]:即时修正描述`；直接注入本次仲裁计算；无则 [] |
| playable | 是否可出牌；默认 true |
| exhaust | 出牌后是否永久消耗（归入消耗堆）；默认 false |
| cost | 出牌费用，消耗行动者当前 energy 点数；默认 1；多数卡应为 1，仅显著强力/多段/高价值效果卡可设为 2；纯功能性/无实质收益卡可设为 0 |
| damage_dealt | 单次命中造成的伤害（以角色攻击力为基数计算；无伤害取 0） |
| energy_delta | 改变目标行动次数（正值增加，负值剥夺）；默认 0 |
| hit_count | 攻击次数（默认 1；多段可设 2~4，每段独立作用） |
| target_type | 出牌目标类型（见下表） |

| target_type | 含义 |
|---|---|
| `{TargetType.ENEMY_SINGLE}` | 攻击单体敌方（默认） |
| `{TargetType.ENEMY_ALL}` | 攻击全体敌方 |
| `{TargetType.ENEMY_RANDOM_MULTI}` | 每段独立随机命中一名敌方（需配合较高 hit_count） |
| `{TargetType.ALLY_SINGLE}` | 治疗/增益单体友方 |
| `{TargetType.ALLY_ALL}` | 治疗/增益全体友方 |
| `{TargetType.SELF_ONLY}` | 仅作用于自身（防御、自损诅咒等） |"""


#######################################################################################################################################
def build_design_principle_prompt(
    num_cards: int,
    keywords: List[str],
    dice_rolls: List[int] = [],
) -> str:
    """生成关键词约束段落。无关键词时输出差异化指引；有骰值时附加于各卡约束行末。"""
    if not keywords:
        return (
            f"关键词约束：无（{num_cards}张卡牌应有差异化，如高伤低防/高防低伤/均衡型）"
        )
    use_dice = len(dice_rolls) == len(keywords)
    header = (
        "关键词约束（按顺序对应；骰值仅在约束中明确说明用法时生效，否则忽略）："
        if use_dice
        else "关键词约束（按顺序对应）："
    )
    lines = "\n".join(
        f"  - 卡牌{i + 1}：{keywords[i]}"
        + (f"（骰值：{dice_rolls[i]}）" if use_dice else "")
        for i in range(len(keywords))
    )
    return f"{header}\n{lines}"


#######################################################################################################################################
def generate_deck_prompt(
    actor_stats: CharacterStats,
    num_cards: int,
    keywords: List[str] = [],
    dice_rolls: List[int] = [],
) -> str:
    """生成战斗开始牌库生成 prompt（含字段说明与 JSON 示例）。"""

    design_principle = build_design_principle_prompt(num_cards, keywords, dice_rolls)

    return f"""\
# 战斗开始：生成 {num_cards} 张初始牌库卡牌

## 角色属性

| HP | 攻击 | 防御 | 每回合行动次数 |
|---|---|---|---|
| {actor_stats.hp}/{actor_stats.max_hp} | {actor_stats.attack} | {actor_stats.defense} | {actor_stats.energy} |

## 设计约束

{design_principle}

{build_card_field_description()}

## 约束

- `description` 禁止提及任何场景地物（如断柱、沙地）、地名或即时情境细节，禁止含数字
- `affixes`/`modifiers` 禁止重述数值字段已确定性表达的效果：`energy_delta ≠ 0` 时不得描述行动次数变化；不得重复量化 `damage_dealt`/`hit_count` 已决定的伤害量级
- `cards` 数组长度必须恰好为 {num_cards}
- 只输出 JSON，不附加任何说明文字

```json
{{
  "cards": [
    {{
      "name": "...",
      "description": "...",
      "affixes": [],
      "modifiers": [],
      "playable": true,
      "exhaust": false,
      "cost": 1,
      "damage_dealt": 0,
      "energy_delta": 0,
      "hit_count": 1,
      "target_type": "enemy_single"
    }}
  ]
}}
```"""


#######################################################################################################################################
def generate_compressed_deck_prompt(
    actor_stats: CharacterStats,
    num_cards: int,
    keywords: List[str] = [],
    dice_rolls: List[int] = [],
) -> str:
    """生成牌库生成 prompt 的压缩版（写入对话历史，减少 token 消耗）。"""
    design_principle = build_design_principle_prompt(num_cards, keywords, dice_rolls)
    return f"""\
# 战斗牌库生成（{num_cards} 张）

HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense} | 行动次数:{actor_stats.energy}

{design_principle}"""


#######################################################################################################################################
