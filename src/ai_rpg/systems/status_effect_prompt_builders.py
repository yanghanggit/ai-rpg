"""StatusEffect 生成提示词构建器模块

集中管理所有用于让 LLM 生成 StatusEffect 的提示词构建函数与相关数据结构，
方便统一阅读与修改 StatusEffect 的生成规则。
"""

from typing import List
from pydantic import BaseModel
from ..models import PhaseType, StatusEffect
from .arbitration_prompt_builders import fmt_duration


#######################################################################################################################################
class AddStatusEffectsResponse(BaseModel):
    """追加状态效果响应"""

    add_effects: List[StatusEffect] = []  # 本次追加的新效果列表


#######################################################################################################################################
def build_status_effect_field_description() -> str:
    """返回 StatusEffect 完整字段说明 Markdown 块（phase 表格 + 所有字段注释）。

    供各提示词构建函数统一引用，避免重复维护。
    """
    return f"""## 状态效果字段说明

每个状态效果必须指定 `phase` 字段，决定生效阶段与消费方。

### `{PhaseType.DRAW}`：本回合抽牌完成后，由下游系统按 `description` 调整已抽手牌

不影响角色属性。`description` 须给出可执行、可量化的规则，明确说明对本回合手牌在费用、伤害、行动次数、命中段数、可出牌性、是否消耗等方面的影响（如"本回合手牌费用 +1"、"本回合手牌造成的伤害 -2"），该文本会在抽牌完成后被下游解析为具体的手牌数值调整，避免笼统模糊的表述。

### `{PhaseType.ARBITRATION}`：每次出牌结算时

例如：「破甲」防御降低；「荆棘」反伤；「眩晕」伤害减少。仅此阶段效果可使用 `counter` 字段：整数初始值，用于条件计数型词条（如"前3次受击"设 3），由仲裁 LLM 按游戏事件更新（倒计型从初始值递减，累加型从 0 递增），默认 0；其余阶段效果保持 `counter` 为 0。

### `{PhaseType.ROUND_END}`：每回合末自动 tick

仅影响 HP。例如：「中毒」每回合末扣血；「燃烧」持续火焰伤害；「再生」每回合末回血（DOT/HOT）。`description` 须是可被下游 LLM 解析的 HP 增减规则，不要在此描述防御、速度等其他数值变化——防御/速度请使用 `defense`/`speed` 字段。

### 通用字段（不区分 phase）

- `duration`：-1=永久，>0=剩余回合数，默认 3
- `speed`：+1 / 0 / -1；持续叠加到角色出手速度，默认 0
- `defense`：整数；持续叠加到角色防御值（正值增防，负值破甲），默认 0
- `description`：第三人称，静态规则说明（客观描述效果机制与数值，不随状态变化）
- 禁止修改 `max_hp`"""


#######################################################################################################################################
def generate_compressed_add_status_effects_prompt(
    current_status_effects: List[StatusEffect],
    current_round_number: int,
    task_hints: List[str],
) -> str:
    """生成压缩版追加状态效果提示词（仅动态感知部分，省略静态字段说明与 JSON 示例）"""

    if len(current_status_effects) == 0:
        effects_list = "无"
    elif len(current_status_effects) <= 3:
        effects_list = "\n".join(
            [
                f"- {effect.name}（{fmt_duration(effect.duration)}）: {effect.description}"
                for effect in current_status_effects
            ]
        )
    else:
        effects_list = "、".join(
            [
                f"{effect.name}（{fmt_duration(effect.duration)}）"
                for effect in current_status_effects
            ]
        )

    hints_block = "\n".join(f"{i + 1}. {h}" for i, h in enumerate(task_hints))
    max_effects = len(task_hints)

    return f"""# 第 {current_round_number} 回合 — 追加状态效果

回顾上下文历史，结合当前已有状态效果，追加本回合应有的新状态效果。

## 任务提示（每条提示对应一个状态效果，严格 1:1）

{hints_block}

## 当前状态效果

{effects_list}

**要求**：不重复现有效果，恰好追加 {max_effects} 个（与上方提示条数一一对应）；无新增时输出空数组。"""


#######################################################################################################################################
def generate_add_status_effects_prompt(
    current_status_effects: List[StatusEffect],
    current_round_number: int,
    task_hints: List[str],
) -> str:
    """生成追加状态效果提示词

    要求 agent 回顾上下文历史并结合当前已有状态，追加本回合应有的新状态效果。
    每条 task_hint 对应一个待生成的状态效果（严格 1:1）。

    Args:
        current_status_effects: 当前已有的状态效果列表
        current_round_number: 当前回合数
        task_hints: 任务提示列表，每条对应一个待生成的状态效果

    Returns:
        格式化的提示词字符串
    """

    # 效果少时展示完整描述；过多时仅列名称以节省 token
    if len(current_status_effects) == 0:
        effects_list = "无"
    elif len(current_status_effects) <= 3:
        effects_list = "\n".join(
            [
                f"- {effect.name}（{fmt_duration(effect.duration)}）: {effect.description}"
                for effect in current_status_effects
            ]
        )
    else:
        effects_list = "、".join(
            [
                f"{effect.name}（{fmt_duration(effect.duration)}）"
                for effect in current_status_effects
            ]
        )

    hints_block = "\n".join(f"{i + 1}. {h}" for i, h in enumerate(task_hints))
    max_effects = len(task_hints)

    return f"""# 第 {current_round_number} 回合 — 追加状态效果

回顾上下文历史，结合当前已有状态效果，追加本回合应有的新状态效果。

## 任务提示（每条提示对应一个状态效果，严格 1:1）

{hints_block}

## 当前状态效果

{effects_list}

{build_status_effect_field_description()}

**要求**：不重复现有效果，恰好追加 {max_effects} 个（与上方提示条数一一对应）；只输出 JSON。

```json
{{
  "add_effects": [
    {{
      "name": "效果名（≤8字）",
      "description": "规则说明（客观描述效果机制与数值，如：每回合末损失 2 HP；前3次受击伤害变为 1）",
      "duration": 3,
      "phase": "round_end",
      "speed": 0,
      "defense": 0,
      "counter": 0
    }}
  ]
}}
```"""


#######################################################################################################################################
