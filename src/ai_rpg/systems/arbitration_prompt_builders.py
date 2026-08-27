"""仲裁提示词构建器模块。"""

from dataclasses import dataclass
from typing import Dict, Final, List, final

from pydantic import BaseModel

from ..utils import prompt_builder
from ..models import (
    Card,
    CharacterStats,
    ConsumableItem,
    GearItem,
    TargetType,
)

#######################################################################################################################################
# 共享仲裁响应数据模型
#######################################################################################################################################


@final
class ArbitrationEntityFinalStats(BaseModel):
    hp: float


@final
class ArbitrationResponse(BaseModel):
    combat_log: str
    final_stats: Dict[str, ArbitrationEntityFinalStats]
    narrative: str
    stage_description: str = (
        ""  # 仲裁后场景环境快照（写入 StageDescriptionComponent.narrative）
    )


#######################################################################################################################################
# 共享格式化工具函数
#######################################################################################################################################


@prompt_builder
def fmt_duration(duration: int) -> str:
    return "永久" if duration == -1 else f"剩余{duration}回合"


@prompt_builder
def fmt_stat_bonuses(stats: CharacterStats) -> str:
    return (
        f"HP {stats.hp:+d} | MAX_HP {stats.max_hp:+d} | ATK {stats.attack:+d} | "
        f"DEF {stats.defense:+d}"
    )


@prompt_builder
def build_stats_update_notification(final_hp: int, max_hp: int) -> str:
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


#######################################################################################################################################
# 提示词段落构建器
#######################################################################################################################################


@prompt_builder
def build_target_stats_lines(
    target_stats: Dict[str, CharacterStats],
    show_defense: bool = False,
) -> str:
    """构建目标信息段落：名称、HP，可选防御。"""
    if not target_stats:
        return "- 无目标"
    target_line_parts = []
    for name, stats in target_stats.items():
        if show_defense:
            line = f"- {name}（HP {stats.hp}/{stats.max_hp} | 防御:{stats.defense}）"
        else:
            line = f"- {name}（HP {stats.hp}/{stats.max_hp}）"
        target_line_parts.append(line)
    return "\n".join(target_line_parts)


@prompt_builder
def build_target_full_stats_lines(
    target_stats: Dict[str, CharacterStats],
) -> str:
    """构建目标完整有效属性段落（卡牌仲裁专用）。

    数据来源必须为 compute_effective_stats 的聚合结果（即 collect_target_character_stats
    的返回值），不使用 CharacterStatsComponent.stats 原始值。
    """
    if not target_stats:
        return "- 无目标"
    return "\n".join(
        f"- {name}（HP {stats.hp}/{stats.max_hp} | ATK {stats.attack} | "
        f"DEF {stats.defense}）"
        for name, stats in target_stats.items()
    )


@prompt_builder
def build_round_action_info_lines(
    action_order: List[str] | None,
    completed_actors: List[str] | None,
    current_actor: str | None,
) -> str:
    """构建回合行动信息段落（卡牌仲裁专用，仅作背景信息，不改变结算规则）。"""
    order_text = " → ".join(action_order) if action_order else "无"
    completed_text = "、".join(completed_actors) if completed_actors else "无"
    current_text = current_actor if current_actor else "无"
    return (
        f"- 行动顺序：{order_text}\n"
        f"- 已完成行动者：{completed_text}\n"
        f"- 当前行动者：{current_text}"
    )


@prompt_builder
def build_instant_affix_section(title: str, affixes: List[str]) -> str:
    """构建「即时词缀」段落（卡牌/消耗品仲裁专用）；affixes 为空时返回空字符串。"""
    if not affixes:
        return ""
    return f"\n\n## {title}\n\n" + "\n".join(f"- {a}" for a in affixes)


@prompt_builder
def build_gear_play_section(gear_item: GearItem | None) -> str:
    """构建出牌者装备段落（含装备即时词缀）；无装备时返回空字符串。"""
    if gear_item is None:
        return ""
    section = (
        f"\n\n## 出牌者装备\n\n"
        f"- 名称：{gear_item.name}\n"
        f"- 描述：{gear_item.description}"
    )
    return section + build_instant_affix_section(
        "装备即时词缀", gear_item.on_play_affixes
    )


FINAL_STATS_DESCRIPTION: Final[
    str
] = """### final_stats

必须包含**本次行动的行动者与所有目标**——即使 HP 无变化也须列出并保持原值，不得包含场内无关角色，格式：
```json
{"角色全名": {"hp": 数值}}
```
- hp：0 ≤ hp ≤ 最大 HP"""


NARRATIVE_DESCRIPTION: Final[
    str
] = """### narrative

60-120 字，第三人称外部视角，纯感官描写，无数字/术语/内心。
应结合本次行动「描述/叙事」中的意象进行故事化展开（如卡牌的叙事锚点、消耗品/装备的感官描述），使演出与该行动的气质一致。
若本次行动涉及与场景对象的交互（取用、触发、破坏、移动、部分使用等），叙述中须体现该对象在交互后的**物理状态变化**（如"碎石散落殆尽"、"机关齿轮转动一格发出咔哒声"、"绳索断裂后仍有一截悬挂在梁上"），使后续上下文能推断其当前可用性与剩余状态。"""


STAGE_DESCRIPTION_DESCRIPTION: Final[
    str
] = """### stage_description

在「当前场景环境」基础上，输出本次行动结束后的**完整环境快照**（第三人称、纯环境描写）。须保留原有环境要素，并融入本次行动造成的物理状态变化（如地面裂痕、墙体破损、药剂溅洒、物件移位或损毁、残留的灼烧/冰冻痕迹等），供后续推断场景当前可用状态。不得提及任何角色本身（不得出现角色名称、角色形态或角色行为）。"""


CALC_RULES_SECTION: Final[
    str
] = """## 计算规则

**卡牌出牌**：单段有效伤害 = max(1, damage − 目标防御)（最低保底 1），共 hit_count 段；出牌者 HP 已为 0 则跳过结算。
**防御**：角色防御 = 基础防御 + 装备加成 + 手牌持有卡牌的 block 之和；本提示中展示的「防御/目标防御」均已按此聚合，直接使用展示值。
**装备穿戴**：stat_bonuses 已由系统确定性写入，无需重复计算。
**消耗品使用**：依物品描述中明确写明的数值计算；描述模糊时给出合理推断并体现在 narrative 中。
**即时词缀**：若本次结算列出即时词缀，以上方结算规则为基础逻辑，结合即时词缀共同考量，务必保证即时词缀被实际执行、不被遗漏；两者如何结合由你发挥判断力自行泛化，不引入词缀未提及的新机制。
**叙事泛化**：本次行动的「描述/叙事」是生成 narrative 与 stage_description 的故事素材——把它与当前场景环境、状态效果、即时词缀结合起来自由泛化（动作、物件、意象、氛围均可），但不得改变上方各结算规则确定的数值结果。

目标 HP = max(0, min(计算后 HP, 最大 HP))"""


#######################################################################################################################################
# SPREAD 专属 prompt 片段（卡牌仲裁用）
#######################################################################################################################################


@dataclass
class SpreadSections:
    """SPREAD 专属 prompt 片段"""

    hit_assignment: str
    log_example: str


def build_spread_sections(
    card: Card,
    targets: List[str],
) -> SpreadSections:
    """为 SPREAD 卡牌构建仲裁 prompt 中的专属片段。

    当 target_type 不是 SPREAD 时，所有字段均为空字符串。
    """
    if card.target_type != TargetType.SPREAD:
        return SpreadSections("", "")

    hit_lines = "\n".join(f"  第{i + 1}击 → {t}" for i, t in enumerate(targets))
    hit_assignment = (
        f"\n## 命中分配（系统预先随机确定，共 {card.hit_count} 击）\n\n"
        f"{hit_lines}\n\n"
        f"按上方命中分配逐段结算，final_stats 须包含**所有被命中过的不重复目标**。"
    )
    log_example = "\nspread 示例：`[英雄|回旋镖→随机:3×3段,敌A×2伤害5,敌B×1伤害3] HP:敌A 15→10 敌B 12→9`"
    return SpreadSections(hit_assignment=hit_assignment, log_example=log_example)


#######################################################################################################################################
# 卡牌仲裁提示词生成器（play_cards）
#######################################################################################################################################


@prompt_builder
def build_combat_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    card: Card,
    targets: List[str],
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    current_stage_description: str,
    gear_item: GearItem | None = None,
    action_order: List[str] | None = None,
    completed_actors: List[str] | None = None,
    current_actor: str | None = None,
) -> str:
    target_lines = build_target_stats_lines(target_stats, show_defense=True)
    target_full_stats_lines = build_target_full_stats_lines(target_stats)
    round_action_info = build_round_action_info_lines(
        action_order, completed_actors, current_actor
    )
    spread = build_spread_sections(card, targets)

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）

## 出牌

- 卡牌：{card.name}
- 叙事（description）：{card.description}
- damage：{card.damage}（单次伤害）
- hit_count：{card.hit_count}（攻击次数）
- self_target：{card.self_target}（是否锁定自身）
{spread.hit_assignment}{build_instant_affix_section("本卡即时词缀", card.on_play_affixes)}{build_gear_play_section(gear_item)}

## 目标

{target_lines}

## 目标有效属性（完整）

{target_full_stats_lines}

## 当前场景环境

{current_stage_description}

## 回合行动信息（背景信息，不改变结算规则）

{round_action_info}

{CALC_RULES_SECTION}

## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_stats": {{}},
  "narrative": "战斗演出",
  "stage_description": "场景环境快照"
}}
```

### combat_log（简名 = 全名最后一段）

正常：`[出牌者简名|卡牌→目标:damage Xx击_count次,伤害Z] HP:目标简名 旧→新`
多段示例：`[英雄|回旋镖→石缝蜥:3x3次,伤害7] HP:石缝蜥 15→8`{spread.log_example}
阵亡跳过：`[出牌者简名|已阵亡，卡牌无法执行]`

{FINAL_STATS_DESCRIPTION}

{NARRATIVE_DESCRIPTION}

{STAGE_DESCRIPTION_DESCRIPTION}"""


@prompt_builder
def build_condensed_combat_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    card: Card,
    targets: List[str],
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    current_stage_description: str,
    gear_item: GearItem | None = None,
    action_order: List[str] | None = None,
    completed_actors: List[str] | None = None,
    current_actor: str | None = None,
) -> str:
    """精简版仲裁提示词，省略静态规则与格式说明，用于写入对话历史减少重复 token。"""
    target_lines = build_target_stats_lines(target_stats, show_defense=True)
    target_full_stats_lines = build_target_full_stats_lines(target_stats)
    round_action_info = build_round_action_info_lines(
        action_order, completed_actors, current_actor
    )
    spread = build_spread_sections(card, targets)

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）

## 出牌

- 卡牌：{card.name}
- 叙事（description）：{card.description}
- damage：{card.damage}（单次伤害）
- hit_count：{card.hit_count}（攻击次数）
- self_target：{card.self_target}（是否锁定自身）
{spread.hit_assignment}{build_instant_affix_section("本卡即时词缀", card.on_play_affixes)}{build_gear_play_section(gear_item)}

## 目标

{target_lines}

## 目标有效属性（完整）

{target_full_stats_lines}

## 当前场景环境

{current_stage_description}

## 回合行动信息（背景信息，不改变结算规则）

{round_action_info}"""


@prompt_builder
def build_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, title: str
) -> str:
    """仲裁广播消息生成器（三类仲裁共用）。"""
    return f"""# 第 {current_round_number} 回合 · {title}

## 演出

{narrative}

## 数据日志

{combat_log}"""


@prompt_builder
def build_combat_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, actor_name: str
) -> str:
    return build_arbitration_broadcast(
        combat_log,
        narrative,
        current_round_number,
        f"{actor_name} 出牌仲裁",
    )


#######################################################################################################################################
# 装备仲裁提示词生成器（equip_gear_item）
#######################################################################################################################################


@prompt_builder
def build_gear_arbitration_prompt(
    item: GearItem,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    current_stage_description: str,
) -> str:
    """生成装备仲裁提示词（完整版）。"""
    target_lines = build_target_stats_lines(target_stats)

    return f"""# 第 {current_round_number} 回合：装备使用结算（以 JSON 格式返回）

## 装备

- 名称：{item.name}
- 描述：{item.description}
- 确定性属性加成（已生效）：{fmt_stat_bonuses(item.stat_bonuses)}

## 目标

{target_lines}

## 当前场景环境

{current_stage_description}

{CALC_RULES_SECTION}

## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_stats": {{}},
  "narrative": "演出描述",
  "stage_description": "场景环境快照"
}}
```

### combat_log（简名 = 全名最后一段）

示例：`[装备寒霜剑→英雄] ATK+3`

{FINAL_STATS_DESCRIPTION}

{NARRATIVE_DESCRIPTION}

{STAGE_DESCRIPTION_DESCRIPTION}"""


@prompt_builder
def build_condensed_gear_arbitration_prompt(
    item: GearItem,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    current_stage_description: str,
) -> str:
    """生成精简版装备仲裁提示词，用于写入对话历史。"""
    target_lines = build_target_stats_lines(target_stats)

    return f"""# 第 {current_round_number} 回合：装备使用结算

## 装备

- 名称：{item.name}
- 描述：{item.description}
- 确定性属性加成（已生效）：{fmt_stat_bonuses(item.stat_bonuses)}

## 目标

{target_lines}

## 当前场景环境

{current_stage_description}"""


@prompt_builder
def build_gear_arbitration_broadcast(
    combat_log: str,
    narrative: str,
    current_round_number: int,
    item_name: str,
) -> str:
    return build_arbitration_broadcast(
        combat_log,
        narrative,
        current_round_number,
        f"穿装备「{item_name}」",
    )


#######################################################################################################################################
# 消耗品仲裁提示词生成器（use_consumable_item）
#######################################################################################################################################


@prompt_builder
def build_consumable_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    item: ConsumableItem,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    current_stage_description: str,
) -> str:
    """生成消耗品仲裁提示词（完整版）。"""
    target_lines = build_target_stats_lines(target_stats)

    # 当使用者不在 target_stats 中（目标为其他角色）时，需单独展示其身份与 HP，
    # 否则仲裁 LLM 无法在 final_stats 中对使用者施加反伤（如目标带「荆棘」）等效果。
    actor_section = (
        f"\n\n## 使用者\n\n{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）"
        if actor_name not in target_stats
        else ""
    )

    return f"""# 第 {current_round_number} 回合：消耗品使用结算（以 JSON 格式返回）

## 消耗品

- 名称：{item.name}
- 描述：{item.description}{actor_section}{build_instant_affix_section("本消耗品即时词缀", item.on_use_affixes)}

## 目标

{target_lines}

## 当前场景环境

{current_stage_description}

{CALC_RULES_SECTION}

## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_stats": {{}},
  "narrative": "演出描述",
  "stage_description": "场景环境快照"
}}
```

### combat_log（简名 = 全名最后一段）

示例：`[治愈药水→英雄] HP:英雄 8→13`
多目标示例：`[鼓舞之酒→队友A,队友B] HP:队友A 8→12,队友B 6→10`

{FINAL_STATS_DESCRIPTION}

{NARRATIVE_DESCRIPTION}

{STAGE_DESCRIPTION_DESCRIPTION}"""


@prompt_builder
def build_condensed_consumable_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    item: ConsumableItem,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    current_stage_description: str,
) -> str:
    """生成精简版消耗品仲裁提示词，用于写入对话历史。"""
    target_lines = build_target_stats_lines(target_stats)

    actor_section = (
        f"\n\n## 使用者\n\n{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）"
        if actor_name not in target_stats
        else ""
    )

    return f"""# 第 {current_round_number} 回合：消耗品使用结算

## 消耗品

- 名称：{item.name}
- 描述：{item.description}{actor_section}{build_instant_affix_section("本消耗品即时词缀", item.on_use_affixes)}

## 目标

{target_lines}

## 当前场景环境

{current_stage_description}"""


@prompt_builder
def build_consumable_arbitration_broadcast(
    combat_log: str,
    narrative: str,
    current_round_number: int,
    item_name: str,
) -> str:
    return build_arbitration_broadcast(
        combat_log,
        narrative,
        current_round_number,
        f"使用消耗品「{item_name}」",
    )
