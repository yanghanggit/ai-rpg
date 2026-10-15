"""仲裁共享提示词模块。

集中承载各类仲裁共用的**共享段落**（计算骨架、受击词缀、工具使用流程、combat_log 格式、
narrative），由出牌仲裁与回合结束仲裁按序拼装；共享规则只在此处定义一处，避免两份提示词
各自漂移。工具名与本次行动者称谓由调用方传入，不在此硬编码。
"""

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
def build_calc_rules_section(
    get_entity_stats_tool: str,
    apply_damage_tool: str,
    kind: ArbitrationKind,
) -> str:
    """计算规则段落（全局骨架）。"""
    actor = _actor_label(kind)
    return f"""## 计算规则（全局骨架）

一次结算含 `hit_count` 次命中，**每次命中各算一次**；一切伤害结算都套用这条骨架，骨架之外不引入新机制。

### 参数（由词缀 / 神器文案指导取值；未提及即取默认）

本卡 `on_play_affixes`、目标 `on_hit_affixes`、神器 `modifiers` 等文案，指导你判定下列参数：

- **伤害系数**（默认 1）调整本卡 `damage`；词缀可要求结合对手状态 / 设定上调（如「对动物 +50%」「带某标记时×2」），依已知外观 / 人设判定；
- **格挡系数**（默认 1）调整目标「总格挡」的抵扣；
- **反伤**（默认 0）：目标方对{actor}的反噬，每击一次，减少{actor} HP（不过总格挡）；
- **吸血 / 治疗**（默认 0）：对{actor}的回复，每击一次，增加{actor} HP。

参数取**非默认值**须在 combat_log 注明依据（如 `[对动物属性 伤害系数2]`）。一切数值只取本次 `{get_entity_stats_tool}` 返回与卡牌字段，禁止引用历史 / 前几回合广播 / 记忆。

### 单次命中与合计（共 hit_count 次）

每击 `命中伤害 = max(0, 本卡 damage × 伤害系数 − 该目标总格挡 × 格挡系数)`，同时各结算一次本击的反伤 / 吸血 / 治疗。
`本卡合计伤害 = Σ 命中伤害`；`合计反伤 / 吸血 / 治疗 = 参数 × hit_count`（词缀明示「一次性」者只计 1 次，依文案）。

### 落账

对每个受影响角色，先算其**净扣减 `amount`**（= 承受伤害 − 获得回复；正=扣血、负=净回复、0=不变），再调用一次 `{apply_damage_tool}`（工具自动 clamp 到 0~最大 HP）：

- 目标：`amount = 本卡合计伤害`
- {actor}：`amount = 合计反伤 − 合计吸血 − 合计治疗`

### 硬约束

- 「本卡合计伤害」= 扣目标 HP 的量 = combat_log 的「伤害 Z」；**> 0 时目标 HP 必须减少**，不存在「被挡下 / 扣减 0」，仅当它恰为 0 时 HP 不变。
- combat_log 的「伤害 Z」必须与 `{apply_damage_tool}` 返回的「本次扣减 Z」**逐字一致**，对不上即算错，须重算后再提交。
- 「总格挡」是角色级数值（其手牌 `block` 之和），不是单牌 `block`。
- {actor}的 HP 为 0 时跳过结算（日志记「已阵亡，卡牌无法执行」）。"""


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
    apply_damage_tool: str,
    submit_tool: str,
    kind: ArbitrationKind,
    holder_name: str = "",
) -> str:
    """工具使用流程段落。"""
    if kind is ArbitrationKind.PLAY_CARDS:
        read_targets = "【出牌者】与【每一个目标】"
    else:
        read_targets = f"【持有者 {holder_name}】与【每一个可能受影响的角色】"
    return f"""## 工具使用流程（严格按顺序，逐行推演，不得跳步）

1. **读**：对{read_targets}各调用一次 {get_entity_stats_tool}，拿到 HP / 最大 HP 与总格挡（可并发多个）。
2. **算**：按「计算规则」骨架逐行推演：先由词缀定出各参数，再逐次命中算出合计伤害与每个角色的净扣减 `amount`，不得跳步或心算省略。
3. **写**：对每个受影响角色调用一次 {apply_damage_tool}，`amount` = 该角色净扣减（正=扣血、负=净回复、0=不变）（可并发多个）。
4. **提交**：调用 {submit_tool} 提交；combat_log 须写出计算过程，其中每个「旧→新」与「伤害 Z」**逐字抄自 {apply_damage_tool} 的返回**（形如「HP 将更新为 7/20（20 → 7，本次扣减 13）」），不得另行心算或改数；无法按骨架结算的词缀原文放进 unsettled_affixes。"""


@prompt_builder
def build_combat_log_section(kind: ArbitrationKind, extra_hint: str = "") -> str:
    """combat_log 字段说明段落（`extra_hint` 供出牌仲裁追加 SPREAD 样例）。"""
    if kind is ArbitrationKind.PLAY_CARDS:
        body = f"""每一段 = 一个受影响角色的 HP 变化，必须显式列出参数取值与代入。**只写最终采用的代入式**，不要写试算 / 自我修正 / 元话述：
- 目标伤害：`[出牌者简名|卡牌→目标简名: D×伤害系数kd − B×格挡系数kb = 每击h × hit_count击 = Z] HP:目标简名 旧→新`
- 反伤 / 吸血 / 治疗：`[来源简名|词缀名→受影响简名: v/击 × hit_count击 = V] HP:受影响简名 旧→新`
- 系数 / 反伤取非默认值时在段内注明依据（如把 `×2` 写成 `×2[对动物属性]`）；阵亡跳过写 `[出牌者简名|已阵亡，卡牌无法执行]`。
示例：`[坏运气|基础攻击→头狼: 5×1−4×1=每击1 ×1击=1] HP:头狼 4→3；[头狼|护喉→坏运气: 反伤2/击 ×1击=2] HP:坏运气 10→8`{extra_hint}"""
    else:
        body = """一段 = 一个受影响角色的 HP 变化，必须显式列出参数取值与代入。**只写最终采用的代入式**，不要写试算 / 自我修正 / 元话述：
`[持有者简名|回合结束·词缀名→目标简名: 参数与代入] HP:目标简名 旧→新`
系数 / 反伤取非默认值时在代入里注明依据（如把 `×2` 写成 `×2[对动物属性]`）。
示例：`[纸人|回合结束·灼烧→英雄: 灼烧2×1−总格挡1×1=1] HP:英雄 15→14`"""
    return f"""### combat_log（简名 = 全名最后一段；**必须写出计算过程**，供核对与向玩家回报）

{body}"""


@prompt_builder
def build_narrative_section() -> str:
    """narrative 字段说明段落。"""
    return """### narrative

60-120 字，第三人称外部视角，纯感官描写，无数字 / 术语 / 内心。
以本次结算所用卡牌的「叙事（description）」为素材，把卡牌意象延展成一段外部可见的动作或现象；不得引入卡牌与其词缀之外的机制。
若卡牌效果改变了某个人或物的状态，描写须体现这一改变，为后续叙事留下可推断的当前状态。"""
