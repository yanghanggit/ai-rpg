"""仲裁公共层：纯计算、共享结果容器、工具 schema 工厂、handler 核心、跨仲裁 builder 与提示词段落。

三种仲裁（出牌 / 回合结束 / 神器）的同名工具跑在同一个 stage 记忆上，参数结构必须一致；
本模块把「结构完全一致、差异仅在标签 / 描述文本」的部分收敛到一处，避免 schema 漂移：

- 纯计算：``compute_damage`` / ``compute_effects``（不依赖游戏对象）；
- ``ArbitrationKind`` 与共享提示词段落：``build_calc_rules_section`` /
  ``build_on_hit_affix_section`` / ``build_tool_flow_section`` /
  ``build_narrative_section`` / ``build_summary_section``；
- ``ArbitrationContext``：统一结果容器（各系统按需取用字段）；
- ``make_*_tool``：工具 schema 工厂（字段结构 + 字段描述统一，工具级 description 由各系统传入）；
- ``get_entity_stats`` / ``resolve_damage`` / ``resolve_effect`` / ``submit_arbitration``：
  与同名工具一一对应的 handler 核心（各仲裁的 ``_handle_*`` 薄包装复用它们）；
- ``pending_hp`` / ``record_segment``：通用 handler 辅助；
- ``build_stats_update_notification`` / ``build_loop_summary_memory`` /
  ``build_arbitration_broadcast``：跨仲裁共用的输出 builder。

各仲裁的状态机（触发、实体解析、HP 落库、RoundEntryKind）与 prompt 数据段仍留在各自
system 文件中。
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ..deepseek import ToolDefinition, ToolFunction
from ..entitas import Entity
from ..game.dbg_combat_processor import (
    compute_character_hand_block,
    compute_character_stats,
)
from ..game.dbg_game import DBGGame
from ..models import Card, HandComponent
from ..utils import prompt_builder

###########################################################################################################################################
# 纯计算（承伤 / 受效）——不依赖游戏对象
###########################################################################################################################################
MINUS = "−"  # U+2212，与 combat_log 既有风格一致
DEFAULT_MULT = 1.0


def _round_half_up(value: float) -> int:
    """四舍五入（half-up），用于把倍率代入后的数值取整。"""
    return int(math.floor(value + 0.5))


def _fmt_mult(value: float) -> str:
    """倍率展示：整数值去掉小数点（如 1.0 → 1）。"""
    return str(int(value)) if float(value).is_integer() else str(value)


###########################################################################################################################################
# 承伤（过格挡）
###########################################################################################################################################
@dataclass(frozen=True)
class DamageResult:
    """一次「承伤」结算结果。`total` 即目标 HP 的净减少量。"""

    hits: int
    per_hit: int
    total: int
    new_hp: int
    expr: str


def compute_damage(
    *,
    base_damage: int,
    hits: int,
    block: int,
    old_hp: int,
    max_hp: int,
    damage_mult: float = DEFAULT_MULT,
    block_mult: float = DEFAULT_MULT,
) -> DamageResult:
    """按骨架公式结算承伤。

    `命中伤害 = max(0, base_damage × damage_mult − block × block_mult)`，逐击求和；
    倍率代入后按四舍五入取整。
    """
    hits = max(0, int(hits))
    damage_mult = max(0.0, float(damage_mult))
    block_mult = max(0.0, float(block_mult))
    effective_damage = _round_half_up(max(0, int(base_damage)) * damage_mult)
    effective_block = _round_half_up(max(0, int(block)) * block_mult)
    per_hit = max(0, effective_damage - effective_block)
    total = per_hit * hits
    new_hp = max(0, min(int(old_hp) - total, int(max_hp)))
    expr = (
        f"{base_damage}×{_fmt_mult(damage_mult)}{MINUS}{block}×{_fmt_mult(block_mult)}"
        f"=每击{per_hit} ×{hits}击={total}"
    )
    return DamageResult(
        hits=hits, per_hit=per_hit, total=total, new_hp=new_hp, expr=expr
    )


###########################################################################################################################################
# 受效（反伤 / 吸血 / 治疗，不过格挡）
###########################################################################################################################################
@dataclass(frozen=True)
class EffectResult:
    """一次「受效」结算结果。`delta` 为净扣减（>0 扣血，<0 净回复）。"""

    hits: int
    reflect: int
    lifesteal: int
    heal: int
    delta: int
    new_hp: int
    expr: str


def compute_effects(
    *,
    base: int,
    hits: int,
    old_hp: int,
    max_hp: int,
    reflect_mult: float = 0.0,
    lifesteal_mult: float = 0.0,
    heal_mult: float = 0.0,
) -> EffectResult:
    """按每击结算某受效角色的反伤 / 吸血 / 治疗。

    各分量 `= 四舍五入(base × 对应倍率)`；`净扣减 = (反伤 − 吸血 − 治疗) × hits`。
    """
    base = int(base)
    hits = max(0, int(hits))
    reflect_mult = max(0.0, float(reflect_mult))
    lifesteal_mult = max(0.0, float(lifesteal_mult))
    heal_mult = max(0.0, float(heal_mult))
    reflect = _round_half_up(base * reflect_mult)
    lifesteal = _round_half_up(base * lifesteal_mult)
    heal = _round_half_up(base * heal_mult)
    delta = (reflect - lifesteal - heal) * hits
    new_hp = max(0, min(int(old_hp) - delta, int(max_hp)))
    parts: list[str] = []
    if reflect:
        parts.append(
            f"反伤{base}×{_fmt_mult(reflect_mult)}={reflect}/击 ×{hits}击={reflect * hits}"
        )
    if lifesteal:
        parts.append(
            f"吸血{base}×{_fmt_mult(lifesteal_mult)}={lifesteal}/击 ×{hits}击={lifesteal * hits}"
        )
    if heal:
        parts.append(
            f"治疗{base}×{_fmt_mult(heal_mult)}={heal}/击 ×{hits}击={heal * hits}"
        )
    if not parts:
        expr = "无 HP 变化"
    elif delta > 0:
        expr = " ".join(parts) + f" = 净扣减{delta}"
    elif delta < 0:
        expr = " ".join(parts) + f" = 净回复{-delta}"
    else:
        expr = " ".join(parts) + " = 0"
    return EffectResult(
        hits=hits,
        reflect=reflect,
        lifesteal=lifesteal,
        heal=heal,
        delta=delta,
        new_hp=new_hp,
        expr=expr,
    )


###########################################################################################################################################
# 共享结果容器
###########################################################################################################################################
class ArbitrationContext(BaseModel):
    """三种仲裁共享的结果容器；各系统按需取用字段（未用到的字段保持默认）。"""

    hp_changes: Dict[str, int] = Field(default_factory=dict)
    pending_hp: Dict[str, int] = Field(default_factory=dict)
    hp_initial: Dict[str, int] = Field(default_factory=dict)
    segments: List[str] = Field(default_factory=list)
    combat_log: Optional[str] = None
    narrative: Optional[str] = None
    summary: Optional[str] = None
    unsettled_affixes: List[str] = Field(default_factory=list)


###########################################################################################################################################
# 通用 handler 辅助
###########################################################################################################################################
def collect_hand_cards_with(entity: Entity, affix_field: str) -> List[Card]:
    """收集角色手牌中在指定词缀字段上非空的卡牌（持有期间参与对应时机的仲裁）。"""
    hand = entity.get(HandComponent) if entity.has(HandComponent) else None
    if hand is None:
        return []
    return [card for card in hand.cards if getattr(card, affix_field)]


def pending_hp(ctx: ArbitrationContext, entity: Entity) -> int:
    """取该实体在本次仲裁中的当前 HP（首次访问时以真实 HP 初始化）。"""
    if entity.name not in ctx.pending_hp:
        ctx.pending_hp[entity.name] = compute_character_stats(entity).hp
    return ctx.pending_hp[entity.name]


def record_segment(
    ctx: ArbitrationContext, entity_name: str, new_hp: int, segment: str
) -> str:
    """记录一次结算：更新运行中 HP、登记最终 HP、追加日志段，返回该段供工具回显。"""
    ctx.pending_hp[entity_name] = new_hp
    ctx.hp_changes[entity_name] = new_hp
    ctx.segments.append(segment)
    return segment


def get_entity_stats(
    game: DBGGame, entity_name: str, *, on_hit_cards: bool = False
) -> str:
    """「获取状态工具」核心：返回 HP / 总格挡；``on_hit_cards=True`` 时附上受击卡牌。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"

    stats = compute_character_stats(entity)
    hand_block = compute_character_hand_block(entity)
    lines = [
        f"【{entity_name}】",
        f"- HP：{stats.hp}/{stats.max_hp}",
        f"- 总格挡（角色级＝该角色手牌 block 之和；结算伤害时只减这个数）：{hand_block}",
    ]
    if on_hit_cards:
        hit_cards = collect_hand_cards_with(entity, "on_hit_affixes")
        if hit_cards:
            cards_str = "\n".join(
                f"    - {c.name}（source={c.source or '未知'}, description={c.description}, "
                f"cost={c.cost}, damage={c.damage}, hit_count={c.hit_count}, "
                f"单牌 block={c.block}, 受击词缀={c.on_hit_affixes}）"
                for c in hit_cards
            )
        else:
            cards_str = "    - 无"
        lines.append(
            "- 受击卡牌（仅列出带受击词缀的卡牌，不是完整手牌；下面每张卡的 `单牌 block` "
            "只是它自己那张牌的格挡值，**不是**上面的总格挡）："
        )
        lines.append(cards_str)
    return "\n".join(lines)


def _target_guard_error(entity_name: str, require_entity: str) -> str:
    return (
        f"错误：本时机目标恒为 {require_entity}，不能结算 {entity_name}。"
        f"请对 {require_entity} 重新调用。"
    )


def resolve_damage(
    game: DBGGame,
    ctx: ArbitrationContext,
    *,
    actor_label: str,
    entity_name: str,
    base_damage: int,
    hits: int,
    damage_mult: float = 1.0,
    block_mult: float = 1.0,
    rationale: str = "",
    require_entity: Optional[str] = None,
) -> str:
    """「承伤结算」核心：读取目标总格挡，交由纯计算模块算伤害并登记日志段。

    ``require_entity`` 非空时校验目标恒为该实体（回合结束仲裁用）。
    """
    if require_entity is not None and entity_name != require_entity:
        return _target_guard_error(entity_name, require_entity)
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"
    stats = compute_character_stats(entity)
    old_hp = pending_hp(ctx, entity)
    result = compute_damage(
        base_damage=int(base_damage),
        hits=int(hits),
        block=compute_character_hand_block(entity),
        old_hp=old_hp,
        max_hp=stats.max_hp,
        damage_mult=float(damage_mult),
        block_mult=float(block_mult),
    )
    note = f"（{rationale}）" if rationale else ""
    segment = (
        f"[{actor_label}→{entity_name}: {result.expr}{note}]"
        f" HP:{entity_name} {old_hp}→{result.new_hp}"
    )
    return record_segment(ctx, entity_name, result.new_hp, segment)


def resolve_effect(
    game: DBGGame,
    ctx: ArbitrationContext,
    *,
    entity_name: str,
    base: int,
    hits: int,
    reflect_mult: float = 0.0,
    lifesteal_mult: float = 0.0,
    heal_mult: float = 0.0,
    rationale: str = "",
    require_entity: Optional[str] = None,
) -> str:
    """「受效结算」核心：反伤 / 吸血 / 治疗按 base×系数、每击，由纯计算模块算净扣减。"""
    if require_entity is not None and entity_name != require_entity:
        return _target_guard_error(entity_name, require_entity)
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"
    stats = compute_character_stats(entity)
    old_hp = pending_hp(ctx, entity)
    result = compute_effects(
        base=int(base),
        hits=int(hits),
        old_hp=old_hp,
        max_hp=stats.max_hp,
        reflect_mult=float(reflect_mult),
        lifesteal_mult=float(lifesteal_mult),
        heal_mult=float(heal_mult),
    )
    note = f"（{rationale}）" if rationale else ""
    segment = (
        f"[{entity_name}: {result.expr}{note}]"
        f" HP:{entity_name} {old_hp}→{result.new_hp}"
    )
    return record_segment(ctx, entity_name, result.new_hp, segment)


def submit_arbitration(
    ctx: ArbitrationContext,
    combat_log: str,
    narrative: str,
    summary: str,
    unsettled_affixes: Optional[List[str]] = None,
) -> str:
    """「提交仲裁结果工具」核心：记录 narrative / summary / combat_log / 未结算项。

    combat_log 由调用方语义决定：出牌 / 回合结束仲裁由系统据 resolve 调用生成（传空即可），
    神器仲裁由 LLM 写效果说明。
    """
    ctx.narrative = narrative
    ctx.summary = summary
    ctx.combat_log = combat_log or None
    if unsettled_affixes:
        ctx.unsettled_affixes = [str(a) for a in unsettled_affixes if str(a).strip()]
    return "仲裁结果已提交"


###########################################################################################################################################
# 跨仲裁共享 builder
###########################################################################################################################################
@prompt_builder
def build_stats_update_notification(final_hp: int, max_hp: int) -> str:
    """发给受影响角色的「生命值已更新」通知。"""
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


def build_loop_summary_memory(summary: str, combat_log: str) -> str:
    """把 LLM 的压缩总结与系统生成的数据日志拼成一条长期记忆。"""
    return f"{summary}\n\n## 数据日志\n{combat_log}"


@prompt_builder
def build_arbitration_broadcast(
    round_number: int, title_label: str, narrative: str, combat_log: str
) -> str:
    """仲裁广播消息生成器（“第 N 回合 · <title_label>”，title_label 由各系统拼好）。"""
    return f"""# 第 {round_number} 回合 · {title_label}

## 演出

{narrative}

## 数据日志

{combat_log}"""


###########################################################################################################################################
# 仲裁类型与共享提示词段落
###########################################################################################################################################
class ArbitrationKind(StrEnum):
    """仲裁类型。

    出牌仲裁与回合结束仲裁的结算原则完全一致，仅「发起阶段」与对行动者的称谓不同；
    本枚举用于让共享段落按类型选用正确的称谓（出牌者 / 持有者）。
    """

    PLAY_CARDS = "play_cards"
    TURN_END = "turn_end"
    AUTONOMOUS = "autonomous"


@prompt_builder
def build_calc_rules_section(get_entity_stats_tool: str, kind: ArbitrationKind) -> str:
    """结算规则段落：说明「数值由系统算、LLM 只选 base 与系数」及系数清单。"""
    if kind is ArbitrationKind.TURN_END:
        target = "持有者"
        affixes = "`on_turn_end_affixes`"
    elif kind is ArbitrationKind.AUTONOMOUS:
        target = "目标"
        affixes = "`on_autonomous_affixes` / `on_hit_affixes`"
    else:
        target = "目标"
        affixes = "`on_play_affixes` / `on_hit_affixes` / 神器 `modifiers`"
    return f"""## 结算规则（数值由系统计算）

系统按固定骨架代你完成**全部算术**：

- **承伤**（过格挡）：`每击伤害 = max(0, base_damage × 伤害系数 − {target}总格挡 × 格挡系数)`，逐击求和；
- **受效**（反伤 / 吸血 / 治疗，不过格挡）：`各分量 = 四舍五入(base × 对应系数)`，`净扣减 = (反伤 − 吸血 − 治疗) × hit_count`。

你要做三件事：为每条效果选定 **base**、判定**各系数取值**、并**说明依据**。

### base 与系数

- **base / base_damage**：affix 引用的那个数值（通常取本卡 `damage` / `block` 字段，或文案明示的数字）。系统**不解释字段语义**，由你依文案判断它代表什么。
- 系数（由 {affixes} 等文案指导；未提及即取默认）：
  - **伤害系数**（默认 1）调整 `base_damage`；**格挡系数**（默认 1）调整{target}总格挡的抵扣（取 `0` 表示无视格挡）；
  - **反伤系数 / 吸血系数 / 治疗系数**（默认 0）作用在 `base` 上得到每击数值。
  词缀可要求结合{target}状态 / 设定上调（如「对动物 +50%」→ 伤害系数 1.5），依已知外观 / 人设判定。

### 硬约束

- 只判定 **base 与系数**；骨架表达不了的机制（固定值以外的特殊算法、按比例、抽牌 / 回能 / 额外行动等）**不要硬塞**，把词缀原文放进 `unsettled_affixes`。
- 一切数值只取本次 `{get_entity_stats_tool}` 返回与卡牌字段，禁止引用历史 / 前几回合广播 / 记忆。
- 「总格挡」是角色级数值（其手牌 `block` 之和），不是单牌 `block`。
- 任一结算对象的 HP 为 0 时跳过结算。"""


@prompt_builder
def build_on_hit_affix_section(get_entity_stats_tool: str) -> str:
    """受击词缀段落（仅出牌仲裁使用；回合结束仲裁不处理 on_hit）。"""
    return f"""## 受击词缀

{get_entity_stats_tool} 返回的「受击卡牌」仅列出带受击词缀的卡牌，不是完整手牌；其 `block` 只是单牌格挡值，角色总格挡以返回的「总格挡」为准。
受击词缀仅在**该实体是本次出牌的目标**时触发；出牌者自身的受击词缀不触发（除非出牌者也同时是目标）。多条须**逐条全部结算**，结算对象是**本次出牌者**，与目标是否阵亡无关（目标被击倒也要照常结算）。依文案结算（如 [反伤] 即骨架里的「反伤」，使出牌者 HP 减少、不过总格挡），数值取其文案明示字段，不引入词缀未提及的新机制。"""


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
        read_step = (
            f"对【出牌者】与【每一个目标】各调用一次 {get_entity_stats_tool}，"
            "拿到 HP / 最大 HP 与总格挡（可并发多个）。"
        )
        judge_step = "逐条读词缀，为每个受影响角色定出 base 与系数（伤害 / 格挡 / 反伤 / 吸血 / 治疗）及依据。"
        calc_step = (
            f"调用 {resolve_damage_tool}（承伤，每个承伤目标一次）与 {resolve_effect_tool}"
            "（反伤 / 吸血 / 治疗，每个受效角色一次）；**数值由系统计算**，你只填 base、系数与依据，"
            "无需自行心算。工具返回规范化的「旧→新」，可直接引用。"
        )
    elif kind is ArbitrationKind.AUTONOMOUS:
        read_step = (
            f"对【持有者】与【每一个可能受影响的目标】各调用一次 {get_entity_stats_tool}，"
            "拿到 HP / 最大 HP、总格挡与受击卡牌（可并发多个）。"
        )
        judge_step = (
            "逐条读自主词缀，按词缀文本确定每条的目标（场上任意存活角色：敌对 / 友方 / 持有者，"
            "可要求随机 / 血量最低等），并为每个受影响角色定出 base 与系数及依据。"
        )
        calc_step = (
            f"调用 {resolve_damage_tool}（承伤，每个承伤目标一次）与 {resolve_effect_tool}"
            "（反伤 / 吸血 / 治疗，每个受效角色一次）；**数值由系统计算**，你只填 base、系数与依据，"
            "无需自行心算。工具返回规范化的「旧→新」，可直接引用。"
        )
    else:
        read_step = f"调用 {get_entity_stats_tool} 读取【持有者 {holder_name}】的 HP / 最大 HP 与总格挡。"
        judge_step = "逐条读词缀，为持有者定出 base 与系数（伤害 / 格挡 / 反伤 / 吸血 / 治疗）及依据。"
        calc_step = (
            f"调用 {resolve_damage_tool}（承伤）与 {resolve_effect_tool}（反伤 / 吸血 / 治疗）；"
            "目标恒为持有者本人，**数值由系统计算**，你只填 base、系数与依据，无需自行心算。"
            "工具返回规范化的「旧→新」，可直接引用。"
        )
    return f"""## 工具使用流程（严格按顺序）

1. **读**：{read_step}
2. **判**：{judge_step}
3. **算**：{calc_step}
4. **提交**：调用 {submit_tool} 提交 `narrative` 与 `unsettled_affixes`；combat_log 由系统据第 3 步自动生成，此字段传空字符串 `""` 即可。"""


@prompt_builder
def build_narrative_section() -> str:
    """narrative 字段说明段落。"""
    return """### narrative

60-120 字，第三人称外部视角，纯感官描写，无数字 / 术语 / 内心。
以本次结算所用卡牌的「叙事（description）」为素材，把卡牌意象延展成一段外部可见的动作或现象；不得引入卡牌与其词缀之外的机制。
若卡牌效果改变了某个人或物的状态，描写须体现这一改变，为后续叙事留下可推断的当前状态。"""


@prompt_builder
def build_summary_section() -> str:
    """summary 字段说明段落：把本次过程压缩成可长期留存的记忆。"""
    return """### summary

本次仲裁的**压缩性总结**：它将**整段替换**本次完整的工具调用轨迹，作为你后续的长期记忆留存。请写清：
- 谁对谁做了什么（含 source / 出牌者 / 目标）；
- 造成或恢复了多少（沿用系统回显的「旧→新」数值，不得改写）；
- 是否有角色被击倒；
- 是否有未结算项。
自然语言、紧凑、自包含，便于未来据此判断「累计伤害到 X」一类条件；数值必须与数据日志一致，不得漂移。"""


###########################################################################################################################################
# 工具 schema 工厂
#
# 字段结构与字段描述在各仲裁间统一（避免同名工具 schema 漂移导致 LLM 传错字段）；
# 工具级 description 由各系统按自身语境传入。
###########################################################################################################################################
def make_get_entity_stats_tool(description: str) -> ToolDefinition:
    """构造 get_entity_stats 工具。"""
    return ToolDefinition(
        function=ToolFunction(
            name="get_entity_stats",
            description=description,
            parameters={
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "角色全名，如 角色.无名 或 怪物.纸俑甲",
                    },
                },
                "required": ["entity_name"],
            },
        )
    )


def make_resolve_damage_tool(description: str) -> ToolDefinition:
    """构造 resolve_damage 工具（base 与系数由 LLM 选，算术由系统做）。"""
    return ToolDefinition(
        function=ToolFunction(
            name="resolve_damage",
            description=description,
            parameters={
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "承伤目标全名",
                    },
                    "base_damage": {
                        "type": "integer",
                        "description": "伤害的基础数值（照抄卡牌 damage 字段，或文案明示的数字）",
                    },
                    "hits": {
                        "type": "integer",
                        "description": "该目标本次承受的命中次数（照抄卡牌 hit_count；SPREAD 卡为命中分配中该目标的出现次数）",
                    },
                    "damage_mult": {
                        "type": "number",
                        "description": "伤害系数（默认 1）",
                    },
                    "block_mult": {
                        "type": "number",
                        "description": "格挡系数（默认 1；0 表示无视格挡）",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "该目标 base 与系数的取值依据（如「对动物属性×2」）",
                    },
                },
                "required": ["entity_name", "base_damage", "hits"],
            },
        )
    )


def make_resolve_effect_tool(description: str) -> ToolDefinition:
    """构造 resolve_effect 工具（反伤 / 吸血 / 治疗，算术由系统做）。"""
    return ToolDefinition(
        function=ToolFunction(
            name="resolve_effect",
            description=description,
            parameters={
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "受效角色全名（不限阵营：反伤常作用于受击方，治疗可作用于任意角色）",
                    },
                    "base": {
                        "type": "integer",
                        "description": "affix 引用的基础数值（通常为本卡 damage / block 字段值，或文案明示的数字）",
                    },
                    "hits": {
                        "type": "integer",
                        "description": "本次结算的命中次数（即对应卡牌的 hit_count）",
                    },
                    "reflect_mult": {
                        "type": "number",
                        "description": "反伤系数（默认 0）：每击反伤 = base × 本系数，使该角色 HP 减少",
                    },
                    "lifesteal_mult": {
                        "type": "number",
                        "description": "吸血系数（默认 0）：每击吸血 = base × 本系数，使该角色 HP 增加",
                    },
                    "heal_mult": {
                        "type": "number",
                        "description": "治疗系数（默认 0）：每击治疗 = base × 本系数，使该角色 HP 增加",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "base 与各系数的取值依据（含卡名 / 词缀名）",
                    },
                },
                "required": ["entity_name", "base", "hits"],
            },
        )
    )


# submit_arbitration 的 combat_log 字段描述默认值：出牌 / 回合结束仲裁由系统生成，传空即可。
# 神器仲裁的 combat_log 由 LLM 写效果说明，故允许通过 combat_log_desc 覆盖该字段描述。
_SUBMIT_COMBAT_LOG_DESC: str = (
    "战斗数据日志；本仲裁由系统据 resolve_damage / resolve_effect 的调用自动生成，"
    "此处传空字符串即可。"
)


def make_submit_arbitration_tool(
    description: str, *, combat_log_desc: str = _SUBMIT_COMBAT_LOG_DESC
) -> ToolDefinition:
    """构造 submit_arbitration 工具。

    ``description`` 为工具级说明；``combat_log_desc`` 仅在神器仲裁（combat_log 由 LLM 生成）时覆盖。
    """
    return ToolDefinition(
        function=ToolFunction(
            name="submit_arbitration",
            description=description,
            parameters={
                "type": "object",
                "properties": {
                    "combat_log": {
                        "type": "string",
                        "description": combat_log_desc,
                    },
                    "narrative": {
                        "type": "string",
                        "description": "60-120 字第三人称演出叙事",
                    },
                    "summary": {
                        "type": "string",
                        "description": "本次仲裁的压缩性总结（将整段替换本次完整工具轨迹、作为长期记忆留存）：谁对谁、造成/恢复多少、谁被击倒、有无未结算项；自然语言、紧凑自包含，数值须与数据日志一致。",
                    },
                    "unsettled_affixes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选：无法按本次结算规则处理的原始条目列表（如要求抽牌/回能/额外行动，或凭空叠加没有牌承载的标记），仅供系统统计，不计入结算。",
                    },
                },
                "required": ["combat_log", "narrative", "summary"],
            },
        )
    )
