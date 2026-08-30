"""仲裁提示词构建器模块。"""

from typing import Dict, Final, List, final

from pydantic import BaseModel

from ..models import (
    CharacterStats,
    ConsumableItem,
    GearItem,
)
from ..utils import prompt_builder

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
def build_stats_update_notification(final_hp: int, max_hp: int) -> str:
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


#######################################################################################################################################
# 提示词段落构建器
#######################################################################################################################################


@prompt_builder
def build_target_stats_lines(
    target_stats: Dict[str, CharacterStats],
    # show_defense: bool = False,
) -> str:
    """构建目标信息段落：名称、HP，可选防御。"""
    if not target_stats:
        return "- 无目标"

    # 构建每个目标的状态行，包括名称、HP 和防御。
    target_line_parts = []
    for name, stats in target_stats.items():
        line = f"- {name}（HP {stats.hp}/{stats.max_hp} | 防御:{stats.defense}）"
        target_line_parts.append(line)

    # 将所有目标的状态行拼接为最终段落。
    return "\n".join(target_line_parts)


@prompt_builder
def build_instant_affix_section(title: str, affixes: List[str]) -> str:
    """构建「即时词缀」段落（卡牌/消耗品仲裁专用）；affixes 为空时返回空字符串。"""
    if not affixes:
        return ""
    return f"\n\n## {title}\n\n" + "\n".join(f"- {a}" for a in affixes)


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
若本次行动涉及与场景对象的交互（取用、触发、破坏、移动、部分使用等），叙述中须体现该对象在交互后的**物理状态变化**（如"碎石散落殆尽"、"机关齿轮转动一格发出咔哒声"、"绳索断裂后仍有一截悬挂在梁上"），使后续叙事能推断其当前可用性与剩余状态。"""


STAGE_DESCRIPTION_DESCRIPTION: Final[
    str
] = """### stage_description

在「当前场景环境」基础上，输出本次行动结束后的**完整环境快照**（第三人称、纯环境描写）。须保留原有环境要素，并融入本次行动造成的物理状态变化（如地面裂痕、墙体破损、药剂溅洒、物件移位或损毁、残留的灼烧/冰冻痕迹等），供后续推断场景当前可用状态。不得提及任何角色本身（不得出现角色名称、角色形态或角色行为）。"""


CALC_RULES_SECTION: Final[
    str
] = """## 计算规则

**卡牌出牌**：单段有效伤害 = max(0, damage − 目标防御)，共 hit_count 段；出牌者 HP 为 0 则跳过结算。
**防御**：本提示中展示的「防御/目标防御」已聚合完成，直接使用展示值。
**消耗品使用**：依物品描述中明确写明的数值计算；描述模糊时给出合理推断并体现在 narrative 中。
**即时词缀**：若列出即时词缀，须确保其被实际执行；可与结算规则泛化结合，但不引入词缀未提及的新机制。
**叙事泛化**：将「描述/叙事」作为 narrative 与 stage_description 的素材，结合场景环境、状态效果、即时词缀自由泛化，但不得改变以上结算规则确定的数值结果。

目标 HP = max(0, min(计算后 HP, 最大 HP))"""


#######################################################################################################################################
# 仲裁广播生成器
#######################################################################################################################################


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
- 描述：{item.description}{actor_section}

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
- 描述：{item.description}{actor_section}

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
