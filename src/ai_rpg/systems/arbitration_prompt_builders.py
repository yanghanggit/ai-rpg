"""仲裁提示词构建器模块。"""

from typing import Dict, Final, List, final
from pydantic import BaseModel
from ..models import (
    AffixTrigger,
    Card,
    CharacterStats,
    ConsumableItem,
    StatusEffect,
    TargetType,
    GearItem,
)
from dataclasses import dataclass

#######################################################################################################################################
# 共享仲裁响应数据模型
#######################################################################################################################################


@final
class ArbitrationStatusEffectPatch(BaseModel):
    name: str
    counter: int


@final
class ArbitrationEntityFinalStats(BaseModel):
    hp: float
    status_effect_patches: List[ArbitrationStatusEffectPatch] = []


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


def fmt_duration(duration: int) -> str:
    return "永久" if duration == -1 else f"剩余{duration}回合"


def fmt_effects(effects: List[StatusEffect]) -> str:
    if not effects:
        return "  无"
    return "\n".join(
        f"  - {e.name}（{fmt_duration(e.duration)}）: {e.description}" for e in effects
    )


def fmt_stat_bonuses(stats: CharacterStats) -> str:
    return (
        f"HP {stats.hp:+d} | MAX_HP {stats.max_hp:+d} | ATK {stats.attack:+d} | "
        f"DEF {stats.defense:+d} | ENERGY {stats.energy:+d} | SPD {stats.speed:+d}"
    )


def stats_update_notification(final_hp: int, max_hp: int) -> str:
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


def fmt_stat_bonuses_compact(stats: CharacterStats) -> str:
    """仅显示非零属性的精简格式，用于 AffixTrigger 单行上下文。"""
    parts: List[str] = []
    if stats.hp:
        parts.append(f"HP{stats.hp:+d}")
    if stats.max_hp:
        parts.append(f"MAXHP{stats.max_hp:+d}")
    if stats.attack:
        parts.append(f"ATK{stats.attack:+d}")
    if stats.defense:
        parts.append(f"DEF{stats.defense:+d}")
    if stats.energy:
        parts.append(f"ENERGY{stats.energy:+d}")
    if stats.speed:
        parts.append(f"SPD{stats.speed:+d}")
    return " ".join(parts) if parts else "无属性变化"


#######################################################################################################################################
# 提示词段落构建器
#######################################################################################################################################


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


def build_arbitration_effects_lines(
    target_arbitration_effects: Dict[str, List[StatusEffect]],
) -> str:
    """构建目标仲裁状态效果段落（装备/消耗品仲裁专用，仅含目标）。"""
    if not target_arbitration_effects:
        return "无"
    lines_parts = []
    for t_name, t_effects in target_arbitration_effects.items():
        lines_parts.append(f"**{t_name}**:\n{fmt_effects(t_effects)}")
    return "\n\n".join(lines_parts)


def build_combat_arbitration_effects_lines(
    actor_name: str,
    actor_arbitration_effects: List[StatusEffect],
    target_arbitration_effects: Dict[str, List[StatusEffect]],
) -> str:
    """构建出牌者+目标仲裁状态效果段落（卡牌仲裁专用）。"""
    lines = f"**出牌者 —— {actor_name}**:\n{fmt_effects(actor_arbitration_effects)}"
    for t_name, t_effects in target_arbitration_effects.items():
        lines += f"\n\n**目标 —— {t_name}**:\n{fmt_effects(t_effects)}"
    return lines


FINAL_STATS_DESCRIPTION: Final[
    str
] = """### final_stats

必须包含**本次行动的行动者与所有目标**——即使 HP 无变化也须列出并保持原值，不得包含场内无关角色，格式：
```json
{"角色全名": {"hp": 数值, "status_effect_patches": []}}
```
- hp：0 ≤ hp ≤ 最大 HP
- status_effect_patches：仅在本次仲裁改变了某效果的 counter 值时填写，格式：
  `{"name": "效果名", "counter": <新整数值>}`
  - name 必须与"仲裁状态效果"中列出的名称完全一致
  - 未改变 counter 的效果不输出；若本次仲裁未触发任何 counter 变化，保持空数组 []"""


NARRATIVE_DESCRIPTION: Final[
    str
] = """### narrative

60-120 字，第三人称外部视角，纯感官描写，无数字/术语/内心。
若本次行动涉及与场景对象的交互（取用、触发、破坏、移动、部分使用等），叙述中须体现该对象在交互后的**物理状态变化**（如"碎石散落殆尽"、"机关齿轮转动一格发出咔哒声"、"绳索断裂后仍有一截悬挂在梁上"），使后续上下文能推断其当前可用性与剩余状态。"""


STAGE_DESCRIPTION_DESCRIPTION: Final[
    str
] = """### stage_description

在「当前场景环境」基础上，输出本次行动结束后的**完整环境快照**（第三人称、纯环境描写）。须保留原有环境要素，并融入本次行动造成的物理状态变化（如地面裂痕、墙体破损、药剂溅洒、物件移位或损毁、残留的灼烧/冰冻痕迹等），供后续推断场景当前可用状态。不得提及任何角色本身（不得出现角色名称、角色形态或角色行为）。"""


CALC_RULES_SECTION: Final[
    str
] = """## 计算规则

**卡牌出牌**：单段有效伤害 = max(1, damage_dealt − 目标防御)（最低保底 1），共 hit_count 段；出牌者 HP 已为 0 则跳过结算。
**装备穿戴**：stat_bonuses 已由系统确定性写入，无需重复计算。
**消耗品使用**：依物品描述中明确写明的数值计算；描述模糊时给出合理推断并体现在 narrative 中。

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


def generate_combat_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    card: Card,
    targets: List[str],
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    actor_arbitration_effects: List[StatusEffect],
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    current_stage_description: str,
) -> str:
    target_lines = build_target_stats_lines(target_stats, show_defense=True)
    arbitration_effects_lines = build_combat_arbitration_effects_lines(
        actor_name, actor_arbitration_effects, target_arbitration_effects
    )
    spread = build_spread_sections(card, targets)

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）

## 出牌

- 卡牌：{card.name}
- damage_dealt：{card.damage_dealt}（单次伤害）
- hit_count：{card.hit_count}（攻击次数）
{spread.hit_assignment}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

## 当前场景环境

{current_stage_description}

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


def generate_compressed_combat_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    card: Card,
    targets: List[str],
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    actor_arbitration_effects: List[StatusEffect],
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    current_stage_description: str,
) -> str:
    """压缩版仲裁提示词，省略静态规则与格式说明，用于写入对话历史减少重复 token。"""
    target_lines = build_target_stats_lines(target_stats, show_defense=True)
    arbitration_effects_lines = build_combat_arbitration_effects_lines(
        actor_name, actor_arbitration_effects, target_arbitration_effects
    )
    spread = build_spread_sections(card, targets)

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）

## 出牌

- 卡牌：{card.name}
- damage_dealt：{card.damage_dealt}（单次伤害）
- hit_count：{card.hit_count}（攻击次数）
{spread.hit_assignment}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

## 当前场景环境

{current_stage_description}"""


def generate_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, title: str
) -> str:
    """仲裁广播消息生成器（三类仲裁共用）。"""
    return f"""# 第 {current_round_number} 回合 · {title}

## 演出

{narrative}

## 数据日志

{combat_log}"""


def generate_combat_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, actor_name: str
) -> str:
    return generate_arbitration_broadcast(
        combat_log,
        narrative,
        current_round_number,
        f"{actor_name} 出牌仲裁",
    )


#######################################################################################################################################
# 装备仲裁提示词生成器（use_gear_item）
#######################################################################################################################################


def generate_gear_arbitration_prompt(
    item: GearItem,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    current_stage_description: str,
) -> str:
    """生成装备仲裁提示词（完整版）。"""
    target_lines = build_target_stats_lines(target_stats)
    arbitration_effects_lines = build_arbitration_effects_lines(
        target_arbitration_effects
    )

    return f"""# 第 {current_round_number} 回合：装备使用结算（以 JSON 格式返回）

## 装备

- 名称：{item.name}
- 描述：{item.description}
- 确定性属性加成（已生效）：{fmt_stat_bonuses(item.stat_bonuses)}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

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


def generate_compressed_gear_arbitration_prompt(
    item: GearItem,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    current_stage_description: str,
) -> str:
    """生成压缩版装备仲裁提示词，用于写入对话历史。"""
    target_lines = build_target_stats_lines(target_stats)
    arbitration_effects_lines = build_arbitration_effects_lines(
        target_arbitration_effects
    )

    return f"""# 第 {current_round_number} 回合：装备使用结算

## 装备

- 名称：{item.name}
- 描述：{item.description}
- 确定性属性加成（已生效）：{fmt_stat_bonuses(item.stat_bonuses)}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

## 当前场景环境

{current_stage_description}"""


def generate_gear_arbitration_broadcast(
    combat_log: str,
    narrative: str,
    current_round_number: int,
    item_name: str,
) -> str:
    return generate_arbitration_broadcast(
        combat_log,
        narrative,
        current_round_number,
        f"穿装备「{item_name}」",
    )


#######################################################################################################################################
# 消耗品仲裁提示词生成器（use_consumable_item）
#######################################################################################################################################


def generate_consumable_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    item: ConsumableItem,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    current_stage_description: str,
) -> str:
    """生成消耗品仲裁提示词（完整版）。"""
    target_lines = build_target_stats_lines(target_stats)
    arbitration_effects_lines = build_arbitration_effects_lines(
        target_arbitration_effects
    )

    # 攻击性消耗品（target_type 非 SELF）时使用者不在 target_stats 中，需单独展示其身份与 HP，
    # 否则仲裁 LLM 无法在 final_stats 中对使用者施加反伤（如目标带「荆棘」）等效果。
    actor_section = (
        f"\n\n## 使用者\n\n{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）"
        if actor_name not in target_stats
        else ""
    )

    return f"""# 第 {current_round_number} 回合：消耗品使用结算（以 JSON 格式返回）

## 消耗品

- 名称：{item.name}
- 描述：{item.description}{actor_section}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

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


def generate_compressed_consumable_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    item: ConsumableItem,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    current_stage_description: str,
) -> str:
    """生成压缩版消耗品仲裁提示词，用于写入对话历史。"""
    target_lines = build_target_stats_lines(target_stats)
    arbitration_effects_lines = build_arbitration_effects_lines(
        target_arbitration_effects
    )

    actor_section = (
        f"\n\n## 使用者\n\n{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）"
        if actor_name not in target_stats
        else ""
    )

    return f"""# 第 {current_round_number} 回合：消耗品使用结算

## 消耗品

- 名称：{item.name}
- 描述：{item.description}{actor_section}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

## 当前场景环境

{current_stage_description}"""


def generate_consumable_arbitration_broadcast(
    combat_log: str,
    narrative: str,
    current_round_number: int,
    item_name: str,
) -> str:
    return generate_arbitration_broadcast(
        combat_log,
        narrative,
        current_round_number,
        f"使用消耗品「{item_name}」",
    )


#######################################################################################################################################
# AffixTrigger 生成器（统一 compact one-liner 格式，B+C+D）
#######################################################################################################################################


def generate_play_cards_affix_triggers(
    actor_name: str,
    card: Card,
    targets: List[str],
) -> List[AffixTrigger]:
    """生成卡牌词缀（card.affixes）对应的 AffixTrigger 列表。

    仅携带原始词缀文本与触发上下文，具体提示词措辞由 AddStatusEffectsActionSystem 统一拼装。
    伤害/HP 变化已经通过仲裁广播（combat_log）与个人 HP 更新通知同步给相关实体，此处无需重复。
    """
    if not card.affixes:
        return []
    targets_str = "、".join(targets) or "无"
    context = f"{actor_name}的「{card.name}」→{targets_str}"
    return [
        AffixTrigger(source="卡牌", context=context, affix=affix)
        for affix in card.affixes
    ]


def generate_gear_on_hit_affix_triggers(
    actor_name: str,
    card_name: str,
    gear_item: GearItem,
) -> List[AffixTrigger]:
    """生成装备 on_hit_affixes 对应的 AffixTrigger 列表（仅目标视角）。

    HP 变化已经通过仲裁广播与个人 HP 更新通知同步给该实体，此处无需重复。
    """
    if not gear_item.on_hit_affixes:
        return []
    context = f"{actor_name}持「{gear_item.name}」命中（「{card_name}」）"
    return [
        AffixTrigger(source="装备命中·受击者", context=context, affix=affix)
        for affix in gear_item.on_hit_affixes
    ]


def generate_gear_equip_affix_triggers(
    item: GearItem,
    targets: List[str],
) -> List[AffixTrigger]:
    """生成装备穿戴 equip_affixes 对应的 AffixTrigger 列表。"""
    if not item.equip_affixes:
        return []
    targets_str = "、".join(targets) or "无"
    stats_str = fmt_stat_bonuses_compact(item.stat_bonuses)
    context = f"「{item.name}」→{targets_str}（{stats_str}）"
    return [
        AffixTrigger(source="装备穿戴", context=context, affix=affix)
        for affix in item.equip_affixes
    ]


def generate_consumable_affix_triggers(
    item: ConsumableItem,
    targets: List[str],
) -> List[AffixTrigger]:
    """生成消耗品 affixes 对应的 AffixTrigger 列表。"""
    if not item.affixes:
        return []
    targets_str = "、".join(targets) or "无"
    context = f"「{item.name}」→{targets_str}"
    return [
        AffixTrigger(source="消耗品", context=context, affix=affix)
        for affix in item.affixes
    ]
