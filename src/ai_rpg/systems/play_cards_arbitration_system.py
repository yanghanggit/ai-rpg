"""战斗仲裁动作系统模块。"""

from dataclasses import dataclass
from functools import partial
from typing import Dict, Final, List, Optional, final

from loguru import logger
from overrides import override
from pydantic import BaseModel, Field

from ..deepseek import (
    LOOP_END_ATTR,
    LOOP_ID_ATTR,
    ToolDefinition,
    ToolFunction,
    agent_loop,
)
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_hand_block,
    compute_character_stats,
    set_character_hp,
)
from ..game.dbg_game import DBGGame
from ..models import (
    Card,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    HandComponent,
    HumanMessage,
    PlayCardsAction,
    RoundEntryKind,
    RoundStatsComponent,
    TargetType,
    render_labeled_str_list,
)
from ..utils import prompt_builder
from .arbitration_calculator import compute_damage, compute_effects
from .arbitration_prompt_builders import (
    ArbitrationKind,
    build_calc_rules_section,
    build_narrative_section,
    build_on_hit_affix_section,
    build_summary_section,
    build_tool_flow_section,
)


###########################################################################################################################################
# 仲裁提示词构建器（play_cards 专属）
###########################################################################################################################################
@dataclass
class _SpreadSections:
    """SPREAD 专属 prompt 片段"""

    hit_assignment: str


def _build_spread_sections(
    card: Card,
    targets: List[str],
) -> _SpreadSections:
    """为 SPREAD 卡牌构建仲裁 prompt 中的专属片段。

    当 target_type 不是 SPREAD 时，字段为空字符串。命中分配由系统预先随机确定，
    每个 `resolve_damage` 调用的 `hits` 应填该目标在此分配中的出现次数。
    """
    if card.target_type != TargetType.SPREAD:
        return _SpreadSections("")

    hit_lines = "\n".join(f"  第{i + 1}击 → {t}" for i, t in enumerate(targets))
    hit_assignment = (
        f"\n## 命中分配（系统预先随机确定，共 {card.hit_count} 击）\n\n"
        f"{hit_lines}\n\n"
        f"对每个被命中的不重复目标调用一次 {RESOLVE_DAMAGE_TOOL.function.name}，`hits` 填该目标在上表中的出现次数。"
    )
    return _SpreadSections(hit_assignment=hit_assignment)


@prompt_builder
def _build_round_action_info_lines(
    action_order: List[str] | None,
    completed_actors: List[str] | None,
    current_actor: str | None,
) -> str:
    """构建回合行动信息段落（仅作背景信息，不改变结算规则）。"""
    order_text = " → ".join(action_order) if action_order else "无"
    completed_text = "、".join(completed_actors) if completed_actors else "无"
    current_text = current_actor if current_actor else "无"
    return (
        f"- 行动顺序：{order_text}\n"
        f"- 已完成行动者：{completed_text}\n"
        f"- 当前行动者：{current_text}"
    )


@prompt_builder
def _build_card_data_lines(card: Card) -> str:
    """输出一张卡参与仲裁的数值字段（词缀单列于「即时词缀」段，来源与叙事一并带上）。"""
    lines = [
        f"- 卡牌：{card.name}",
        f"- source（来源/注入者）：{card.source or '未知'}",
        f"- 叙事（description）：{card.description}",
        f"- cost：{card.cost}",
        f"- damage（本卡单次伤害）：{card.damage}",
        f"- hit_count（本卡攻击次数）：{card.hit_count}",
        f"- block（本卡单牌格挡值）：{card.block}",
    ]
    return "\n".join(lines)


@prompt_builder
def _build_combat_arbitration_tool_prompt(
    actor_name: str,
    card: Card,
    targets: List[str],
    current_round_number: int,
    action_order: List[str] | None = None,
    completed_actors: List[str] | None = None,
    current_actor: str | None = None,
) -> str:

    # 构建本回合的战斗仲裁工具 prompt，包括出牌者信息、本卡数据、目标信息、回合行动信息等。
    unique_targets = list(dict.fromkeys(targets))

    # 构建目标信息段落。
    target_names = "、".join(unique_targets) if unique_targets else "无"

    # 构建回合行动信息段落。
    round_action_info = _build_round_action_info_lines(
        action_order, completed_actors, current_actor
    )

    # 构建 SPREAD 卡牌的专属仲裁片段。
    spread = _build_spread_sections(card, targets)

    return f"""# 第 {current_round_number} 回合：战斗结算（工具调用模式）

## 出牌者

{actor_name}

## 本卡数据（本卡 = 本次实际打出的牌）

{_build_card_data_lines(card)}
{spread.hit_assignment}

## 即时词缀（共 {len(card.on_play_affixes)} 条，逐条结算，一条都不能漏）

{render_labeled_str_list("- 即时词缀", card.on_play_affixes, indent="    ")}

即时词缀是逐条独立规则：**逐条全部读取**，判断它为你给出的哪些系数取值（伤害系数 / 格挡系数 / 反伤 / 吸血 / 治疗等），用于后续判定；不得合并、省略，也不引入词缀未提及的新机制。

## 目标

{target_names}

## 回合行动信息（背景信息，不改变结算规则）

{round_action_info}

{build_calc_rules_section(GET_ENTITY_STATS_TOOL.function.name, ArbitrationKind.PLAY_CARDS)}

{build_on_hit_affix_section(GET_ENTITY_STATS_TOOL.function.name)}

## source 字段

`source` = 卡牌来源（生成 / 注入者），空串表示未知；副本保留原 `source`。词缀可据持有者与 `source` 的关系设生效条件：`本卡持有者` 无条件；`source 者` 仅当持有者 == 本卡 `source` 时结算；`非 source 者` 仅当持有者 != 本卡 `source` 时结算；条件不成立则整条跳过（不计入 `unsettled_affixes`）。

{build_tool_flow_section(GET_ENTITY_STATS_TOOL.function.name, RESOLVE_DAMAGE_TOOL.function.name, RESOLVE_EFFECT_TOOL.function.name, SUBMIT_ARBITRATION_TOOL.function.name, ArbitrationKind.PLAY_CARDS)}

## {SUBMIT_ARBITRATION_TOOL.function.name} 字段说明

{build_narrative_section()}

{build_summary_section()}"""


@prompt_builder
def _build_combat_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, actor_name: str
) -> str:
    """出牌仲裁的广播消息生成器（第 N 回合 · <出牌者> 出牌仲裁）。"""
    return f"""# 第 {current_round_number} 回合 · {actor_name} 出牌仲裁

## 演出

{narrative}

## 数据日志

{combat_log}"""


@prompt_builder
def _build_stats_update_notification(final_hp: int, max_hp: int) -> str:
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


def _build_loop_summary_memory(summary: str, combat_log: str) -> str:
    """把 LLM 的压缩总结与系统生成的数据日志拼成一条长期记忆。"""
    return f"{summary}\n\n## 数据日志\n{combat_log}"


###########################################################################################################################################
# 仲裁工具定义
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_entity_stats",
        description="读取指定战斗角色的当前生命值（HP/最大HP）与总格挡（其手牌 block 之和）及其手牌中带受击词缀的卡牌（含这些卡牌的 source/damage/hit_count/block 等数据）。用于获取发起者与目标当前状态。",
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


RESOLVE_DAMAGE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="resolve_damage",
        description="结算某目标承受的伤害：系统按 max(0, base_damage×damage_mult − 该目标总格挡×block_mult) 逐击计算（共 hits 次）并落库。你只需选定 base 与系数。对每个承伤目标调用一次。",
        parameters={
            "type": "object",
            "properties": {
                "entity_name": {"type": "string", "description": "承伤目标全名"},
                "base_damage": {
                    "type": "integer",
                    "description": "伤害的基础数值（照抄卡牌 damage 字段，或文案明示的数字）",
                },
                "hits": {
                    "type": "integer",
                    "description": "该目标本次承受的命中次数（非 SPREAD 卡为 hit_count；SPREAD 卡为命中分配中该目标的出现次数）",
                },
                "damage_mult": {"type": "number", "description": "伤害系数（默认 1）"},
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


RESOLVE_EFFECT_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="resolve_effect",
        description="结算某受效角色的反伤 / 吸血 / 治疗（均按每击 ×hits，不过格挡）：系统按「各分量 = 四舍五入(base × 对应系数)」计算净扣减并落库。对每个受效角色调用一次。",
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


SUBMIT_ARBITRATION_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_arbitration",
        description="提交本次仲裁的最终结果（战斗日志、演出叙事、无法结算的词缀）。调用后本次仲裁结束。",
        parameters={
            "type": "object",
            "properties": {
                "combat_log": {
                    "type": "string",
                    "description": "战斗数据日志；本仲裁由系统据 resolve_damage / resolve_effect 的调用自动生成，此处传空字符串即可。",
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
                    "description": "可选：无法按上述计算规则结算的词缀原文列表（如要求抽牌/回能/额外行动，或凭空叠加没有牌承载的标记），仅供系统统计，不计入结算。",
                },
            },
            "required": ["combat_log", "narrative", "summary"],
        },
    )
)


###########################################################################################################################################
# 仲裁工具 handler
###########################################################################################################################################
class _ArbitrationContext(BaseModel):
    """仲裁工具 handler 的共享结果容器。"""

    hp_changes: Dict[str, int] = Field(default_factory=dict)
    pending_hp: Dict[str, int] = Field(default_factory=dict)
    segments: List[str] = Field(default_factory=list)
    narrative: Optional[str] = None
    summary: Optional[str] = None
    unsettled_affixes: List[str] = Field(default_factory=list)


###########################################################################################################################################
def _collect_hand_on_hit_cards(entity: Entity) -> List[Card]:
    """收集角色手牌中所有带受击词缀的卡牌（持有期间参与受击仲裁）。"""
    hand = entity.get(HandComponent) if entity.has(HandComponent) else None
    if hand is None:
        return []
    return [card for card in hand.cards if card.on_hit_affixes]


###########################################################################################################################################
def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """处理「获取状态工具」调用：返回 HP/总格挡 + 参与受击仲裁的手牌卡牌数据。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"

    stats = compute_character_stats(entity)
    hand_block = compute_character_hand_block(entity)

    # 收集角色手牌中所有带受击词缀的卡牌（持有期间参与受击仲裁）
    hit_cards = _collect_hand_on_hit_cards(entity)
    if hit_cards:
        cards_str = "\n".join(
            f"    - {c.name}（source={c.source or '未知'}, description={c.description}, cost={c.cost}, "
            f"damage={c.damage}, hit_count={c.hit_count}, 单牌 block={c.block}, 受击词缀={c.on_hit_affixes}）"
            for c in hit_cards
        )
    else:
        cards_str = "    - 无"

    return (
        f"【{entity_name}】\n"
        f"- HP：{stats.hp}/{stats.max_hp}\n"
        f"- 总格挡（角色级＝该角色手牌 block 之和；结算伤害时只减这个数）：{hand_block}\n"
        f"- 受击卡牌（仅列出带受击词缀的卡牌，不是完整手牌；下面每张卡的 `单牌 block` 只是它自己那张牌的格挡值，**不是**上面的总格挡）：\n"
        f"{cards_str}"
    )


def _pending_hp(ctx: _ArbitrationContext, entity: Entity) -> int:
    """取该实体在本次仲裁中的当前 HP（首次访问时以真实 HP 初始化）。"""
    if entity.name not in ctx.pending_hp:
        ctx.pending_hp[entity.name] = compute_character_stats(entity).hp
    return ctx.pending_hp[entity.name]


def _record_segment(
    ctx: _ArbitrationContext, entity_name: str, new_hp: int, segment: str
) -> str:
    """记录一次结算：更新运行中 HP、登记最终 HP、追加日志段，返回该段供工具回显。"""
    ctx.pending_hp[entity_name] = new_hp
    ctx.hp_changes[entity_name] = new_hp
    ctx.segments.append(segment)
    return segment


def _handle_resolve_damage(
    game: DBGGame,
    ctx: _ArbitrationContext,
    card: Card,
    actor_name: str,
    entity_name: str,
    base_damage: int,
    hits: int,
    damage_mult: float = 1.0,
    block_mult: float = 1.0,
    rationale: str = "",
) -> str:
    """处理「承伤结算」：读取目标总格挡，交由纯计算模块算出伤害并登记。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"
    stats = compute_character_stats(entity)
    old_hp = _pending_hp(ctx, entity)
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
        f"[{actor_name}|{card.name}→{entity_name}: {result.expr}{note}]"
        f" HP:{entity_name} {old_hp}→{result.new_hp}"
    )
    return _record_segment(ctx, entity_name, result.new_hp, segment)


def _handle_resolve_effect(
    game: DBGGame,
    ctx: _ArbitrationContext,
    entity_name: str,
    base: int,
    hits: int,
    reflect_mult: float = 0.0,
    lifesteal_mult: float = 0.0,
    heal_mult: float = 0.0,
    rationale: str = "",
) -> str:
    """处理「受效结算」：反伤 / 吸血 / 治疗按 base×系数、每击，由纯计算模块算净扣减。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"
    stats = compute_character_stats(entity)
    old_hp = _pending_hp(ctx, entity)
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
    return _record_segment(ctx, entity_name, result.new_hp, segment)


def _handle_submit_arbitration(
    ctx: _ArbitrationContext,
    combat_log: str,
    narrative: str,
    summary: str,
    unsettled_affixes: Optional[List[str]] = None,
) -> str:
    """处理「提交仲裁结果工具」调用。combat_log 由系统根据 resolve 调用生成，入参忽略。"""
    del combat_log
    ctx.narrative = narrative
    ctx.summary = summary
    if unsettled_affixes:
        ctx.unsettled_affixes = [str(a) for a in unsettled_affixes if str(a).strip()]
    return "仲裁结果已提交"


###########################################################################################################################################
@final
class PlayCardsArbitrationSystem(ReactiveProcessor):
    """响应 PlayCardsAction 事件，对单张出牌立即进行 AI 仲裁结算（工具调用模式）。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayCardsAction) and entity.has(RoundStatsComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("PlayCardsArbitrationSystem: 战斗未进行中，跳过仲裁")
            return

        logger.debug(
            f"PlayCardsArbitrationSystem: 触发仲裁，找到 {len(entities)} 个符合条件的出牌实体"
        )

        await self._request_combat_arbitration(entities[0])

    #######################################################################################################################################
    async def _request_combat_arbitration(self, actor_entity: Entity) -> None:
        """驱动单次出牌的完整工具化仲裁流程。"""

        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert stage_entity is not None, f"无法获取 {actor_entity.name} 所在场景实体！"

        assert actor_entity.has(
            PlayCardsAction
        ), f"实体 {actor_entity.name} 缺少 PlayCardsAction 组件！"
        play_cards_action = actor_entity.get(PlayCardsAction)

        assert actor_entity.has(
            RoundStatsComponent
        ), f"出牌实体 {actor_entity.name} 缺少 RoundStatsComponent！"

        # 获取当前回合数，用于仲裁提示生成
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 获取最新回合的行动信息，供仲裁提示词扩展使用
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "仲裁阶段最新回合不应为 None"
        round_action_order = latest_round.action_order
        round_completed_actors = latest_round.completed_actors
        round_current_actor = latest_round.current_actor

        # 生成工具化仲裁提示消息（完整版，供 LLM 首轮使用）
        message = _build_combat_arbitration_tool_prompt(
            actor_entity.name,
            play_cards_action.card,
            play_cards_action.targets,
            current_round_number,
            round_action_order,
            round_completed_actors,
            round_current_actor,
        )

        # 仲裁结果容器：handler 通过 partial 绑定写入，避免闭包。
        ctx = _ArbitrationContext()

        # 本次 loop 的身份标记；结束后据 result 的区间把整段新增记忆压缩为一条总结。
        stage_memory = self._game.get_agent_memory(stage_entity)
        loop_id = (
            f"play_cards:{current_round_number}:"
            f"{actor_entity.name}:{play_cards_action.card.name}"
        )
        loop_start_index = len(stage_memory.messages)

        try:
            result = await agent_loop(
                name=stage_entity.name,
                input_message=message,
                messages=stage_memory.messages,
                tools=[
                    GET_ENTITY_STATS_TOOL,
                    RESOLVE_DAMAGE_TOOL,
                    RESOLVE_EFFECT_TOOL,
                    SUBMIT_ARBITRATION_TOOL,
                ],
                handlers={
                    GET_ENTITY_STATS_TOOL.function.name: partial(
                        _handle_get_entity_stats, self._game
                    ),
                    RESOLVE_DAMAGE_TOOL.function.name: partial(
                        _handle_resolve_damage,
                        self._game,
                        ctx,
                        play_cards_action.card,
                        actor_entity.name,
                    ),
                    RESOLVE_EFFECT_TOOL.function.name: partial(
                        _handle_resolve_effect, self._game, ctx
                    ),
                    SUBMIT_ARBITRATION_TOOL.function.name: partial(
                        _handle_submit_arbitration, ctx
                    ),
                },
                max_rounds=6,
                tool_choice="required",
                terminal_tools=[SUBMIT_ARBITRATION_TOOL],
                loop_id=loop_id,
            )
        except Exception as e:
            logger.error(f"[PlayCardsArbitrationSystem] agent_loop 异常: {e}")
            # 回滚本次 loop 已追加的记忆，避免失败轨迹污染上下文。
            self._game.replace_span(
                stage_entity, loop_start_index, len(stage_memory.messages), []
            )
            return

        if not result or ctx.narrative is None or ctx.summary is None:
            logger.error(
                "[PlayCardsArbitrationSystem] 仲裁未正常完成（未提交结果或达到轮次上限）"
            )
            # 回滚本次 loop 追加的记忆。
            self._game.replace_span(
                stage_entity, result.start_index, result.end_index, []
            )
            return

        # 成功：把本次 loop 新增的整段记忆（prompt + 工具调用轨迹）压缩为一条「总结 + 数据日志」，
        # 并以 loop_id / loop_id_end 标记该总结，供未来反查（如神器「累计伤害到 X」类玩法）。
        combat_log = "；".join(ctx.segments) if ctx.segments else "本回合无 HP 变化"
        self._game.replace_span(
            stage_entity,
            result.start_index,
            result.end_index,
            [
                HumanMessage(
                    content=_build_loop_summary_memory(ctx.summary, combat_log),
                    **{LOOP_ID_ATTR: loop_id, LOOP_END_ATTR: loop_id},
                )
            ],
        )

        # 通知覆盖保证：行动者 + 所有目标（去重，行动者可能同时是目标）都必须收到通知。
        # 若 LLM 未对某个实体调用结算工具（例如其 HP 未变化），则补记其当前 HP，
        # 确保下方统一落库时仍会向其发送「生命值已更新」通知。
        notify_names = list(
            dict.fromkeys([actor_entity.name, *play_cards_action.targets])
        )
        for notify_name in notify_names:
            if notify_name in ctx.hp_changes:
                continue
            entity = self._game.get_actor_entity(notify_name)
            if entity is None:
                logger.error(
                    f"[PlayCardsArbitrationSystem] 无法找到需通知角色: {notify_name}"
                )
                return
            ctx.hp_changes[notify_name] = compute_character_stats(entity).hp

        self._apply_tool_arbitration_result(
            stage_entity,
            actor_entity,
            ctx,
            combat_log,
        )

    #######################################################################################################################################
    def _apply_tool_arbitration_result(
        self,
        stage_entity: Entity,
        actor_entity: Entity,
        ctx: _ArbitrationContext,
        combat_log: str,
    ) -> None:
        """应用工具化仲裁结果：更新 HP，广播仲裁事件，写入回合记录。"""

        assert ctx.narrative is not None, "narrative 不应为 None"
        narrative = ctx.narrative
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"PlayCardsArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 广播当前回合的仲裁结果
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=_build_combat_arbitration_broadcast(
                    combat_log,
                    narrative,
                    current_round_number,
                    actor_entity.name,
                ),
                stage=stage_entity.name,
                combat_log=combat_log,
                narrative=narrative,
            ),
            exclude_entities={stage_entity},
        )

        # 词缀 telemetry：记录仲裁器无法按计算规则结算的词缀
        for affix in ctx.unsettled_affixes:
            logger.warning(
                f"[PlayCardsArbitrationSystem] 词缀无法按计算规则结算（telemetry）: {affix}"
            )

        # 更新每个受影响实体的 HP 状态
        for entity_name, hp in hp_changes.items():
            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到 hp_changes 中的实体: {entity_name}"
            assert entity.has(
                CharacterStatsComponent
            ), f"实体 {entity_name} 缺少 CharacterStatsComponent！"

            old_hp = compute_character_stats(entity).hp
            after_stats = set_character_hp(entity, int(hp))
            new_hp = after_stats.hp
            max_hp = after_stats.max_hp
            logger.info(f"更新 {entity_name} HP: {old_hp} → {new_hp}/{max_hp}")

            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=_build_stats_update_notification(new_hp, max_hp)
                ),
            )

        # 将本回合的战斗日志和叙事内容添加到当前回合的记录中
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "current_rounds 不应为 None"
        latest_round.record(RoundEntryKind.CARDS, combat_log, narrative)

    #######################################################################################################################################
