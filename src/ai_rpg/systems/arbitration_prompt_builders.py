"""仲裁提示词构建器模块。"""

from typing import Dict, Final, List, Optional, final
from pydantic import BaseModel
from ..entitas import Entity
from ..models import (
    PlayCardsAction,
    UseGearItemAction,
    UseConsumableItemAction,
    CharacterStats,
    StatusEffect,
    TargetType,
    GearItem,
    MonsterComponent,
    PartyMemberComponent,
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
    trigger_post_arbitration: bool = False


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


def _fmt_stat_bonuses_compact(stats: CharacterStats) -> str:
    """仅显示非零属性的精简格式，用于 task hint 单行上下文。"""
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
    target_gear_modifiers: Optional[Dict[str, List[str]]] = None,
    show_defense: bool = False,
) -> str:
    """构建目标信息段落：名称、HP，可选防御与装备修正。"""
    if not target_stats:
        return "- 无目标"
    target_line_parts = []
    for name, stats in target_stats.items():
        if show_defense:
            line = f"- {name}（HP {stats.hp}/{stats.max_hp} | 防御:{stats.defense}）"
        else:
            line = f"- {name}（HP {stats.hp}/{stats.max_hp}）"
        if target_gear_modifiers:
            mods = target_gear_modifiers.get(name, [])
            if mods:
                line += "\n  装备修正：" + "、".join(mods)
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


TRIGGER_POST_ARBITRATION_DESCRIPTION: Final[
    str
] = """### trigger_post_arbitration

布尔值，决定是否触发场景干预系统（stage agent 追加状态效果 / 塞牌）。
判断规则：仅当本次行动的 **narrative 叙事中涉及与已存在场景要素的物理交互**（如搅起沙尘、触发机关、破坏地面物件、揭示可借用道具等），且该交互**合理推断可对场内角色产生后续物理影响**时，设为 `true`；
否则（纯角色行动，无环境互动），输出 `false`。"""


FINAL_STATS_DESCRIPTION: Final[
    str
] = """### final_stats

必须包含**所有相关角色**，格式：
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


CALC_RULES_SECTION: Final[
    str
] = """## 计算规则

**卡牌出牌**：单段有效伤害 = max(1, damage_dealt − 目标防御)（最低保底 1），共 hit_count 段；出牌者 HP 已为 0 则跳过结算；当卡牌描述涉及自身减伤/护盾，或仲裁状态效果含反伤规则时，结合上下文决定是否使用出牌者防御。
**装备穿戴**：stat_bonuses 已由系统确定性写入，无需重复计算；仅处理 modifiers 词缀对目标 HP 的叠加影响。
**消耗品使用**：依物品描述中明确写明的数值计算；描述模糊时给出合理推断并体现在 narrative 中。

即时修正词缀（若有）声明的修正规则**叠加**到上述计算之上，在 final_stats 中体现。
目标 HP = max(0, min(计算后 HP, 最大 HP))"""


#######################################################################################################################################
# ENEMY_SPREAD 专属 prompt 片段（卡牌仲裁用）
#######################################################################################################################################


@dataclass
class SpreadSections:
    """ENEMY_SPREAD 专属 prompt 片段"""

    hit_assignment: str
    log_example: str


def build_spread_sections(
    play_cards_action: PlayCardsAction,
) -> SpreadSections:
    """为 ENEMY_SPREAD 卡牌构建仲裁 prompt 中的专属片段。

    当 target_type 不是 ENEMY_SPREAD 时，所有字段均为空字符串。
    """
    if play_cards_action.card.target_type != TargetType.ENEMY_SPREAD:
        return SpreadSections("", "")

    hit_lines = "\n".join(
        f"  第{i + 1}击 → {t}" for i, t in enumerate(play_cards_action.targets)
    )
    hit_assignment = (
        f"\n## 命中分配（系统预先随机确定，共 {play_cards_action.card.hit_count} 击）\n\n"
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
    play_cards_action: PlayCardsAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    actor_arbitration_effects: List[StatusEffect],
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    actor_gear_modifiers: List[str],
    target_gear_modifiers: Dict[str, List[str]],
) -> str:
    target_lines = build_target_stats_lines(
        target_stats, target_gear_modifiers, show_defense=True
    )
    arbitration_effects_lines = build_combat_arbitration_effects_lines(
        actor_name, actor_arbitration_effects, target_arbitration_effects
    )
    spread = build_spread_sections(play_cards_action)

    modifiers = play_cards_action.card.modifiers
    modifiers_line = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {a}" for a in modifiers)
        if modifiers
        else ""
    )
    actor_gear_modifiers_line = (
        "\n- 装备即时修正词缀：\n" + "\n".join(f"  - {m}" for m in actor_gear_modifiers)
        if actor_gear_modifiers
        else ""
    )

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）

## 出牌

- 卡牌：{play_cards_action.card.name}
- damage_dealt：{play_cards_action.card.damage_dealt}（单次伤害）
- hit_count：{play_cards_action.card.hit_count}（攻击次数）
{f'- energy_delta：{play_cards_action.card.energy_delta:+d}（改变目标行动次数，已由系统直接结算）\n' if play_cards_action.card.energy_delta != 0 else ''}{modifiers_line}{actor_gear_modifiers_line}{spread.hit_assignment}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

{CALC_RULES_SECTION}

## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_stats": {{}},
  "narrative": "战斗演出",
  "trigger_post_arbitration": false
}}
```

{TRIGGER_POST_ARBITRATION_DESCRIPTION}

### combat_log（简名 = 全名最后一段）

正常：`[出牌者简名|卡牌→目标:damage Xx击_count次,伤害Z] HP:目标简名 旧→新`
多段示例：`[英雄|回旋镖→石缝蜥:3x3次,伤害7] HP:石缝蜥 15→8`{spread.log_example}
阵亡跳过：`[出牌者简名|已阵亡，卡牌无法执行]`

{FINAL_STATS_DESCRIPTION}

{NARRATIVE_DESCRIPTION}"""


def generate_compressed_combat_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    play_cards_action: PlayCardsAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    actor_arbitration_effects: List[StatusEffect],
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    actor_gear_modifiers: List[str],
    target_gear_modifiers: Dict[str, List[str]],
) -> str:
    """压缩版仲裁提示词，省略静态规则与格式说明，用于写入对话历史减少重复 token。"""
    target_lines = build_target_stats_lines(
        target_stats, target_gear_modifiers, show_defense=True
    )
    arbitration_effects_lines = build_combat_arbitration_effects_lines(
        actor_name, actor_arbitration_effects, target_arbitration_effects
    )
    spread = build_spread_sections(play_cards_action)

    modifiers = play_cards_action.card.modifiers
    modifiers_line = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {a}" for a in modifiers)
        if modifiers
        else ""
    )
    actor_gear_modifiers_line = (
        "\n- 装备即时修正词缀：\n" + "\n".join(f"  - {m}" for m in actor_gear_modifiers)
        if actor_gear_modifiers
        else ""
    )

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）

## 出牌

- 卡牌：{play_cards_action.card.name}
- damage_dealt：{play_cards_action.card.damage_dealt}（单次伤害）
- hit_count：{play_cards_action.card.hit_count}（攻击次数）
{f'- energy_delta：{play_cards_action.card.energy_delta:+d}（改变目标行动次数，已由系统直接结算）\n' if play_cards_action.card.energy_delta != 0 else ''}{modifiers_line}{actor_gear_modifiers_line}{spread.hit_assignment}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}"""


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
    action: UseGearItemAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
) -> str:
    """生成装备仲裁提示词（完整版）。"""
    target_lines = build_target_stats_lines(target_stats)
    arbitration_effects_lines = build_arbitration_effects_lines(
        target_arbitration_effects
    )
    item = action.item
    modifiers_line = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {m}" for m in item.modifiers)
        if item.modifiers
        else ""
    )

    return f"""# 第 {current_round_number} 回合：装备使用结算（以 JSON 格式返回）

## 装备

- 名称：{item.name}
- 描述：{item.description}
- 确定性属性加成（已生效）：{fmt_stat_bonuses(item.stat_bonuses)}{modifiers_line}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

{CALC_RULES_SECTION}

## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_stats": {{}},
  "narrative": "演出描述",
  "trigger_post_arbitration": false
}}
```

{TRIGGER_POST_ARBITRATION_DESCRIPTION}

### combat_log（简名 = 全名最后一段）

示例：`[装备寒霜剑→英雄] ATK+3`

{FINAL_STATS_DESCRIPTION}

{NARRATIVE_DESCRIPTION}"""


def generate_compressed_gear_arbitration_prompt(
    action: UseGearItemAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
) -> str:
    """生成压缩版装备仲裁提示词，用于写入对话历史。"""
    target_lines = build_target_stats_lines(target_stats)
    arbitration_effects_lines = build_arbitration_effects_lines(
        target_arbitration_effects
    )
    item = action.item
    modifiers_line = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {m}" for m in item.modifiers)
        if item.modifiers
        else ""
    )

    return f"""# 第 {current_round_number} 回合：装备使用结算

## 装备

- 名称：{item.name}
- 描述：{item.description}
- 确定性属性加成（已生效）：{fmt_stat_bonuses(item.stat_bonuses)}{modifiers_line}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}"""


def generate_gear_arbitration_broadcast(
    combat_log: str,
    narrative: str,
    current_round_number: int,
    is_party_action: bool,
    item_name: str,
) -> str:
    camp_label = "友方阵营" if is_party_action else "敌方"
    return generate_arbitration_broadcast(
        combat_log,
        narrative,
        current_round_number,
        f"{camp_label}使用装备「{item_name}」",
    )


#######################################################################################################################################
# 消耗品仲裁提示词生成器（use_consumable_item）
#######################################################################################################################################


def generate_consumable_arbitration_prompt(
    action: UseConsumableItemAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    target_gear_modifiers: Dict[str, List[str]],
) -> str:
    """生成消耗品仲裁提示词（完整版）。"""
    target_lines = build_target_stats_lines(target_stats, target_gear_modifiers)
    arbitration_effects_lines = build_arbitration_effects_lines(
        target_arbitration_effects
    )

    modifiers = action.item.modifiers
    modifiers_line = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {m}" for m in modifiers)
        if modifiers
        else ""
    )

    return f"""# 第 {current_round_number} 回合：消耗品使用结算（以 JSON 格式返回）

## 消耗品

- 名称：{action.item.name}
- 描述：{action.item.description}{modifiers_line}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

{CALC_RULES_SECTION}

## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_stats": {{}},
  "narrative": "演出描述",
  "trigger_post_arbitration": false
}}
```

{TRIGGER_POST_ARBITRATION_DESCRIPTION}

### combat_log（简名 = 全名最后一段）

示例：`[治愈药水→英雄] HP:英雄 8→13`
多目标示例：`[鼓舞之酒→队友A,队友B] HP:队友A 8→12,队友B 6→10`

{FINAL_STATS_DESCRIPTION}

{NARRATIVE_DESCRIPTION}"""


def generate_compressed_consumable_arbitration_prompt(
    action: UseConsumableItemAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    target_gear_modifiers: Dict[str, List[str]],
) -> str:
    """生成压缩版消耗品仲裁提示词，用于写入对话历史。"""
    target_lines = build_target_stats_lines(target_stats, target_gear_modifiers)
    arbitration_effects_lines = build_arbitration_effects_lines(
        target_arbitration_effects
    )

    modifiers = action.item.modifiers
    modifiers_line = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {m}" for m in modifiers)
        if modifiers
        else ""
    )

    return f"""# 第 {current_round_number} 回合：消耗品使用结算

## 消耗品

- 名称：{action.item.name}
- 描述：{action.item.description}{modifiers_line}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}"""


def generate_consumable_arbitration_broadcast(
    combat_log: str,
    narrative: str,
    current_round_number: int,
    is_party_action: bool,
    item_name: str,
) -> str:
    camp_label = "友方阵营" if is_party_action else "敌方"
    return generate_arbitration_broadcast(
        combat_log,
        narrative,
        current_round_number,
        f"{camp_label}使用消耗品「{item_name}」",
    )


#######################################################################################################################################
# Task hint 生成器（统一 compact one-liner 格式，B+C+D）
#######################################################################################################################################


def generate_play_cards_actor_task_hints(
    actor_name: str,
    play_cards_action: PlayCardsAction,
) -> List[str]:
    """生成出牌者视角的 AddStatusEffectsAction task_hints（card.affixes）。

    格式：[卡牌·出牌者] 「{card}」→{targets}，{damage}伤×{hits}击；词缀 → {affix}
    """
    card = play_cards_action.card
    if not card.affixes:
        return []
    targets_str = "、".join(play_cards_action.targets) or "无"
    energy_part = f"，能量{card.energy_delta:+d}" if card.energy_delta != 0 else ""
    base = f"[卡牌·出牌者] 「{card.name}」→{targets_str}，{card.damage_dealt}伤×{card.hit_count}击{energy_part}"
    return [f"{base}；词缀 → {affix}" for affix in card.affixes]


def generate_play_cards_target_task_hints(
    actor_name: str,
    play_cards_action: PlayCardsAction,
    new_hp: int,
    max_hp: int,
) -> List[str]:
    """生成受击目标视角的 AddStatusEffectsAction task_hints（card.affixes）。

    格式：[卡牌·受击者] {actor}的「{card}」命中，{damage}伤×{hits}击，HP {new}/{max}；词缀 → {affix}
    补入仲裁后 HP 数据（D），使 LLM 推理更精准。
    """
    card = play_cards_action.card
    if not card.affixes:
        return []
    energy_part = f"，能量{card.energy_delta:+d}" if card.energy_delta != 0 else ""
    base = (
        f"[卡牌·受击者] {actor_name}的「{card.name}」命中，"
        f"{card.damage_dealt}伤×{card.hit_count}击{energy_part}，HP {new_hp}/{max_hp}"
    )
    return [f"{base}；词缀 → {affix}" for affix in card.affixes]


def generate_gear_on_hit_task_hints(
    actor_name: str,
    play_cards_action: PlayCardsAction,
    gear_item: GearItem,
    new_hp: int,
    max_hp: int,
) -> List[str]:
    """生成装备 on_hit_affixes 的 AddStatusEffectsAction task_hints（仅目标视角）。

    格式：[装备命中·受击者] {actor}持「{gear}」命中（「{card}」），HP {new}/{max}；装备词缀 → {affix}
    补入仲裁后 HP 数据（D），填补原缺失上下文。
    """
    if not gear_item.on_hit_affixes:
        return []
    card = play_cards_action.card
    base = (
        f"[装备命中·受击者] {actor_name}持「{gear_item.name}」命中"
        f"（「{card.name}」），HP {new_hp}/{max_hp}"
    )
    return [f"{base}；装备词缀 → {affix}" for affix in gear_item.on_hit_affixes]


def generate_gear_equip_task_hints(
    action: UseGearItemAction,
    entity: Entity,
) -> List[str]:
    """生成装备穿戴 equip_affixes 的 AddStatusEffectsAction task_hints。

    格式：[装备穿戴·{阵营}] 「{item}」→{targets}（{stats}）；词缀 → {affix}
    """
    item = action.item
    if not item.equip_affixes:
        return []
    targets_str = "、".join(action.targets) or "无"
    stats_str = _fmt_stat_bonuses_compact(item.stat_bonuses)
    if entity.has(PartyMemberComponent):
        camp = "友方"
    elif entity.has(MonsterComponent):
        camp = "敌方"
    else:
        camp = "未知"
    base = f"[装备穿戴·{camp}] 「{item.name}」→{targets_str}（{stats_str}）"
    return [f"{base}；词缀 → {affix}" for affix in item.equip_affixes]


def generate_consumable_task_hints(
    action: UseConsumableItemAction,
    entity: Entity,
) -> List[str]:
    """生成消耗品 affixes 的 AddStatusEffectsAction task_hints。

    格式：[消耗品·{阵营}] 「{item}」→{targets}；词缀 → {affix}
    """
    item = action.item
    if not item.affixes:
        return []
    targets_str = "、".join(action.targets) or "无"
    if entity.has(PartyMemberComponent):
        camp = "友方"
    elif entity.has(MonsterComponent):
        camp = "敌方"
    else:
        camp = "未知"
    base = f"[消耗品·{camp}] 「{item.name}」→{targets_str}"
    return [f"{base}；词缀 → {affix}" for affix in item.affixes]
