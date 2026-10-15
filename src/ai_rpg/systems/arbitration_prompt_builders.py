"""仲裁共享提示词模块。"""

from enum import StrEnum

from ..utils import prompt_builder

#######################################################################################################################################
# 仲裁类型
#######################################################################################################################################


class ArbitrationKind(StrEnum):
    """仲裁类型。

    出牌仲裁与回合结束仲裁的结算原则完全一致，仅「发起阶段」与对行动者的称谓不同；
    本枚举用于让共享段落按类型选用正确的称谓（出牌者 / 持有者）。
    """

    PLAY_CARDS = "play_cards"
    TURN_END = "turn_end"


def _actor_label(kind: ArbitrationKind) -> str:
    """本次结算行动者的称谓。"""
    return "出牌者" if kind is ArbitrationKind.PLAY_CARDS else "持有者"


#######################################################################################################################################
# 共享提示词
#######################################################################################################################################


@prompt_builder
def build_calc_rules_section(get_entity_stats_tool: str, kind: ArbitrationKind) -> str:
    """结算规则段落：说明「数值由系统算、LLM 只选 base 与系数」及系数清单。"""
    actor = _actor_label(kind)
    return f"""## 结算规则（数值由系统计算）

系统按固定骨架代你完成**全部算术**：

- **承伤**（过格挡）：`每击伤害 = max(0, base_damage × 伤害系数 − 目标总格挡 × 格挡系数)`，逐击求和；
- **受效**（反伤 / 吸血 / 治疗，不过格挡）：`各分量 = 四舍五入(base × 对应系数)`，`净扣减 = (反伤 − 吸血 − 治疗) × hit_count`。

你要做三件事：为每条效果选定 **base**、判定**各系数取值**、并**说明依据**。

### base 与系数

- **base / base_damage**：affix 引用的那个数值（通常取本卡 `damage` / `block` 字段，或文案明示的数字）。系统**不解释字段语义**，由你依文案判断它代表什么。
- 系数（由 `on_play_affixes` / `on_hit_affixes` / 神器 `modifiers` 等文案指导；未提及即取默认）：
  - **伤害系数**（默认 1）调整 `base_damage`；**格挡系数**（默认 1）调整目标总格挡的抵扣（取 `0` 表示无视格挡）；
  - **反伤系数 / 吸血系数 / 治疗系数**（默认 0）作用在 `base` 上得到每击数值。
  词缀可要求结合对手状态 / 设定上调（如「对动物 +50%」→ 伤害系数 1.5），依已知外观 / 人设判定。

### 硬约束

- 只判定 **base 与系数**；骨架表达不了的机制（固定值以外的特殊算法、按比例、抽牌 / 回能 / 额外行动等）**不要硬塞**，把词缀原文放进 `unsettled_affixes`。
- 一切数值只取本次 `{get_entity_stats_tool}` 返回与卡牌字段，禁止引用历史 / 前几回合广播 / 记忆。
- 「总格挡」是角色级数值（其手牌 `block` 之和），不是单牌 `block`。
- 任一结算对象的 HP 为 0 时跳过结算。"""


@prompt_builder
def build_on_hit_affix_section(
    get_entity_stats_tool: str,
    kind: ArbitrationKind,
    holder_name: str = "",
) -> str:
    """受击词缀段落。"""
    actor = _actor_label(kind)
    if kind is ArbitrationKind.PLAY_CARDS:
        trigger = "本次出牌的目标"
        damage_source = "本次出牌者"
    else:
        trigger = "本次回合结束结算中受到伤害的目标"
        damage_source = f"造成本次伤害的持有者 {holder_name}"
    return f"""## 受击词缀

{get_entity_stats_tool} 返回的「受击卡牌」仅列出带受击词缀的卡牌，不是完整手牌；其 `block` 只是单牌格挡值，角色总格挡以返回的「总格挡」为准。
受击词缀仅在**该实体是{trigger}**时触发；{actor}自身的受击词缀不触发（除非{actor}也同时是{trigger}）。多条须**逐条全部结算**，结算对象是**{damage_source}**，与目标是否阵亡无关（目标被击倒也要照常结算）。依文案结算（如 [反伤] 即骨架里的「反伤」，使{actor} HP 减少、不过总格挡），数值取其文案明示字段，不引入词缀未提及的新机制。"""


@prompt_builder
def build_tool_flow_section(
    get_entity_stats_tool: str,
    resolve_damage_tool: str,
    resolve_effect_tool: str,
    submit_tool: str,
    kind: ArbitrationKind,
    holder_name: str = "",
) -> str:
    """工具使用流程段落。"""
    if kind is ArbitrationKind.PLAY_CARDS:
        read_targets = "【出牌者】与【每一个目标】"
    else:
        read_targets = f"【持有者 {holder_name}】与【每一个可能受影响的角色】"
    return f"""## 工具使用流程（严格按顺序）

1. **读**：对{read_targets}各调用一次 {get_entity_stats_tool}，拿到 HP / 最大 HP 与总格挡（可并发多个）。
2. **判**：逐条读词缀，为每个受影响角色定出 base 与系数（伤害 / 格挡 / 反伤 / 吸血 / 治疗）及依据。
3. **算**：调用 {resolve_damage_tool}（承伤，每个承伤目标一次）与 {resolve_effect_tool}（反伤 / 吸血 / 治疗，每个受效角色一次）；**数值由系统计算**，你只填 base、系数与依据，无需自行心算。工具返回规范化的「旧→新」，可直接引用。
4. **提交**：调用 {submit_tool} 提交 `narrative` 与 `unsettled_affixes`；combat_log 由系统据第 3 步自动生成，此字段传空字符串 `""` 即可。"""


@prompt_builder
def build_narrative_section() -> str:
    """narrative 字段说明段落。"""
    return """### narrative

60-120 字，第三人称外部视角，纯感官描写，无数字 / 术语 / 内心。
以本次结算所用卡牌的「叙事（description）」为素材，把卡牌意象延展成一段外部可见的动作或现象；不得引入卡牌与其词缀之外的机制。
若卡牌效果改变了某个人或物的状态，描写须体现这一改变，为后续叙事留下可推断的当前状态。"""
