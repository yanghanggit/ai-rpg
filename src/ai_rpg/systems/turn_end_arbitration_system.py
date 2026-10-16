"""回合结束仲裁系统模块。

仲裁者与出牌仲裁一致：由**所在场景（stage）**担任，结果写入 stage 记忆并全场景广播；
被结算的是发起 pass turn 的行动者（持有者）手牌中带回合结束词缀的卡牌。
"""

import json
from functools import partial
from typing import Dict, Final, List, Optional, final

from loguru import logger
from overrides import override
from pydantic import BaseModel, Field

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_hand_block,
    compute_character_stats,
    set_character_hp,
)
from ..game.dbg_game import DBGGame
from ..models import (
    AIMessage,
    Card,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    HandComponent,
    HumanMessage,
    PassTurnAction,
    RoundEntryKind,
    render_labeled_str_list,
)
from ..utils import prompt_builder
from .arbitration_calculator import compute_damage, compute_effects
from .arbitration_prompt_builders import (
    ArbitrationKind,
    build_calc_rules_section,
    build_narrative_section,
    build_tool_flow_section,
)


###########################################################################################################################################
# 回合结束仲裁提示词构建器
###########################################################################################################################################
@prompt_builder
def _build_turn_end_card_lines(card: Card) -> str:
    """输出一张带回合结束词缀的卡参与仲裁的数据字段。"""
    source = card.source or "未知"
    lines = [
        f"- 卡牌：{card.name}",
        f"- source（来源/注入者）：{source}",
        f"- 叙事（description）：{card.description}",
        f"- damage（单卡单次伤害）：{card.damage}",
        f"- hit_count（单卡攻击次数）：{card.hit_count}",
        f"- block（本卡单牌格挡值）：{card.block}",
        render_labeled_str_list(
            "- 回合结束词缀", card.on_turn_end_affixes, indent="    "
        ),
    ]
    return "\n".join(lines)


@prompt_builder
def _build_turn_end_arbitration_tool_prompt(
    holder_name: str,
    cards: List[Card],
    current_round_number: int,
) -> str:
    """生成回合结束仲裁提示词（完整版，供 LLM 首轮使用）。"""
    cards_lines = "\n\n".join(_build_turn_end_card_lines(c) for c in cards)

    return f"""# 第 {current_round_number} 回合：回合结束结算（工具调用模式）

## 回合结束的持有者

{holder_name}

其回合结束（pass turn）时，由你结算以下带回合结束词缀的卡牌的效果；**这些效果的目标恒为持有者本人 {holder_name}**。

## 回合结束词缀卡牌

{cards_lines}

{build_calc_rules_section(GET_ENTITY_STATS_TOOL.function.name, ArbitrationKind.TURN_END)}

## 回合结束词缀

{holder_name} 是这些卡牌的持有者；每张卡的 `source` 是它的来源（生成 / 注入者），副本保留原 `source`。词缀的生效条件按持有者与 `source` 的关系判定：`本卡持有者` 无条件（效果落在 {holder_name}）；`source 者` 仅当 {holder_name} == 该卡 `source` 时结算；`非 source 者` 仅当 {holder_name} != 该卡 `source` 时结算；条件不成立则整条跳过。回合结束词缀是逐条独立规则：**逐条全部读取**，判断它为哪些系数取值，用于后续判定；**所有效果只作用于持有者 {holder_name} 本人**，不得指向其他角色，不得合并、省略或引入词缀外机制。

{build_tool_flow_section(GET_ENTITY_STATS_TOOL.function.name, RESOLVE_DAMAGE_TOOL.function.name, RESOLVE_EFFECT_TOOL.function.name, SUBMIT_ARBITRATION_TOOL.function.name, ArbitrationKind.TURN_END, holder_name)}

## {SUBMIT_ARBITRATION_TOOL.function.name} 字段说明

{build_narrative_section()}"""


@prompt_builder
def _build_turn_end_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, holder_name: str
) -> str:
    """回合结束仲裁的广播消息生成器（第 N 回合 · <持有者> 回合结束仲裁）。"""
    return f"""# 第 {current_round_number} 回合 · {holder_name} 回合结束仲裁

## 演出

{narrative}

## 数据日志

{combat_log}"""


@prompt_builder
def _build_stats_update_notification(final_hp: int, max_hp: int) -> str:
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


###########################################################################################################################################
# 仲裁工具定义（本系统独立定义，与 PlayCardsArbitrationSystem 同名但互不共享）
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_entity_stats",
        description="读取指定战斗角色的当前生命值（HP/最大HP）与总格挡（其手牌 block 之和）。用于获取持有者当前状态。",
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
        description="结算持有者承受的伤害：系统按 max(0, base_damage×damage_mult − 持有者总格挡×block_mult) 逐击计算（共 hits 次）并落库。你只需选定 base 与系数。对持有者调用一次。",
        parameters={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "承伤目标全名（本时机恒为持有者本人）",
                },
                "base_damage": {
                    "type": "integer",
                    "description": "伤害的基础数值（照抄卡牌 damage / block 字段，或文案明示的数字）",
                },
                "hits": {
                    "type": "integer",
                    "description": "该目标本次承受的命中次数（照抄卡牌 hit_count）",
                },
                "damage_mult": {"type": "number", "description": "伤害系数（默认 1）"},
                "block_mult": {
                    "type": "number",
                    "description": "格挡系数（默认 1；0 表示无视格挡）",
                },
                "rationale": {
                    "type": "string",
                    "description": "该目标 base 与系数的取值依据（含卡名 / 词缀名）",
                },
            },
            "required": ["entity_name", "base_damage", "hits"],
        },
    )
)


RESOLVE_EFFECT_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="resolve_effect",
        description="结算持有者的反伤 / 吸血 / 治疗（均按每击 ×hits，不过格挡）：系统按「各分量 = 四舍五入(base × 对应系数)」计算净扣减并落库。对持有者调用一次。",
        parameters={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "受效角色全名（本时机恒为持有者本人）",
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
        description="提交本次回合结束仲裁的最终结果（战斗日志、演出叙事、无法结算的词缀）。调用后本次仲裁结束。",
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
                "unsettled_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选：无法按上述计算规则结算的词缀原文列表（如要求抽牌/回能/额外行动，或凭空叠加没有牌承载的标记），仅供系统统计，不计入结算。",
                },
            },
            "required": ["combat_log", "narrative"],
        },
    )
)


###########################################################################################################################################
# 仲裁工具 handler
###########################################################################################################################################
class _TurnEndArbitrationContext(BaseModel):
    """单个持有者回合结束仲裁的共享结果容器。"""

    hp_changes: Dict[str, int] = Field(default_factory=dict)
    pending_hp: Dict[str, int] = Field(default_factory=dict)
    segments: List[str] = Field(default_factory=list)
    narrative: Optional[str] = None
    unsettled_affixes: List[str] = Field(default_factory=list)


def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """处理「获取状态工具」调用：返回 HP/总格挡。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"

    stats = compute_character_stats(entity)
    hand_block = compute_character_hand_block(entity)

    return (
        f"【{entity_name}】\n"
        f"- HP：{stats.hp}/{stats.max_hp}\n"
        f"- 总格挡（角色级＝该角色手牌 block 之和；结算伤害时只减这个数）：{hand_block}"
    )


def _pending_hp(ctx: _TurnEndArbitrationContext, entity: Entity) -> int:
    """取该实体在本次仲裁中的当前 HP（首次访问时以真实 HP 初始化）。"""
    if entity.name not in ctx.pending_hp:
        ctx.pending_hp[entity.name] = compute_character_stats(entity).hp
    return ctx.pending_hp[entity.name]


def _record_segment(
    ctx: _TurnEndArbitrationContext, entity_name: str, new_hp: int, segment: str
) -> str:
    """记录一次结算：更新运行中 HP、登记最终 HP、追加日志段，返回该段供工具回显。"""
    ctx.pending_hp[entity_name] = new_hp
    ctx.hp_changes[entity_name] = new_hp
    ctx.segments.append(segment)
    return segment


def _handle_resolve_damage(
    game: DBGGame,
    ctx: _TurnEndArbitrationContext,
    holder_name: str,
    entity_name: str,
    base_damage: int,
    hits: int,
    damage_mult: float = 1.0,
    block_mult: float = 1.0,
    rationale: str = "",
) -> str:
    """处理「承伤结算」：读取持有者总格挡，交由纯计算模块算出伤害并登记。目标恒为持有者。"""
    if entity_name != holder_name:
        return (
            f"错误：回合结束词缀的目标恒为持有者 {holder_name}，"
            f"不能结算 {entity_name}。请对 {holder_name} 重新调用。"
        )
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
        f"[{holder_name}→{entity_name}: {result.expr}{note}]"
        f" HP:{entity_name} {old_hp}→{result.new_hp}"
    )
    return _record_segment(ctx, entity_name, result.new_hp, segment)


def _handle_resolve_effect(
    game: DBGGame,
    ctx: _TurnEndArbitrationContext,
    holder_name: str,
    entity_name: str,
    base: int,
    hits: int,
    reflect_mult: float = 0.0,
    lifesteal_mult: float = 0.0,
    heal_mult: float = 0.0,
    rationale: str = "",
) -> str:
    """处理「受效结算」：反伤 / 吸血 / 治疗按 base×系数、每击。目标恒为持有者。"""
    if entity_name != holder_name:
        return (
            f"错误：回合结束词缀的目标恒为持有者 {holder_name}，"
            f"不能结算 {entity_name}。请对 {holder_name} 重新调用。"
        )
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
    ctx: _TurnEndArbitrationContext,
    combat_log: str,
    narrative: str,
    unsettled_affixes: Optional[List[str]] = None,
) -> str:
    """处理「提交仲裁结果工具」调用。combat_log 由系统根据 resolve 调用生成，入参忽略。"""
    del combat_log
    ctx.narrative = narrative
    if unsettled_affixes:
        ctx.unsettled_affixes = [str(a) for a in unsettled_affixes if str(a).strip()]
    return "仲裁结果已提交"


###########################################################################################################################################
@final
class TurnEndArbitrationSystem(ReactiveProcessor):
    """响应 PassTurnAction，由所在场景（stage）仲裁行动者手牌中的回合结束词缀。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PassTurnAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PassTurnAction)

    #######################################################################################################################################
    def _collect_hand_turn_end_cards(self, entity: Entity) -> List[Card]:
        """收集角色手牌中所有带回合结束词缀的卡牌（持有期间在回合结束时触发）。"""
        hand = entity.get(HandComponent) if entity.has(HandComponent) else None
        if hand is None:
            return []
        return [card for card in hand.cards if card.on_turn_end_affixes]

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("TurnEndArbitrationSystem: 战斗未进行中，跳过回合结束仲裁")
            return

        if not entities:
            return

        # 以 pass turn 实体定位场景；只处理本次发起 pass turn 的行动者（entities）
        pass_turn_entity = entities[0]
        stage_entity = self._game.resolve_stage_entity(pass_turn_entity)
        assert (
            stage_entity is not None
        ), f"TurnEndArbitrationSystem: 无法找到 {pass_turn_entity.name} 所在的场景实体"

        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 仅处理本次发起 pass turn 的行动者（PassTurnActionSystem 一次只处理一个）
        turn_end_cards = self._collect_hand_turn_end_cards(pass_turn_entity)
        if not turn_end_cards:
            logger.debug(
                "TurnEndArbitrationSystem: 本次 pass turn 的行动者无回合结束词缀卡牌，跳过"
            )
            return

        prompt = _build_turn_end_arbitration_tool_prompt(
            pass_turn_entity.name,
            turn_end_cards,
            current_round_number,
        )
        ctx = _TurnEndArbitrationContext()

        try:
            ok = await agent_loop(
                name=stage_entity.name,
                prompt=prompt,
                messages=self._game.get_agent_memory(stage_entity).messages,
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
                        pass_turn_entity.name,
                    ),
                    RESOLVE_EFFECT_TOOL.function.name: partial(
                        _handle_resolve_effect,
                        self._game,
                        ctx,
                        pass_turn_entity.name,
                    ),
                    SUBMIT_ARBITRATION_TOOL.function.name: partial(
                        _handle_submit_arbitration, ctx
                    ),
                },
                max_rounds=6,
                tool_choice="required",
                terminal_tools=[SUBMIT_ARBITRATION_TOOL],
            )
        except Exception as e:
            logger.error(
                f"TurnEndArbitrationSystem: [{pass_turn_entity.name}] agent_loop 异常: {e}"
            )
            return

        if not ok or ctx.narrative is None:
            logger.error(
                f"TurnEndArbitrationSystem: [{pass_turn_entity.name}] 回合结束仲裁未正常完成，跳过落库"
            )
            return

        self._apply_turn_end_arbitration_result(
            stage_entity,
            pass_turn_entity,
            ctx,
        )

    #######################################################################################################################################
    def _apply_turn_end_arbitration_result(
        self,
        stage_entity: Entity,
        holder: Entity,
        ctx: _TurnEndArbitrationContext,
    ) -> None:
        """应用单个持有者的回合结束仲裁结果：写场景记忆、更新受影响角色 HP、全场景广播。"""

        assert ctx.narrative is not None, "narrative 不应为 None"
        combat_log = (
            "；".join(ctx.segments) if ctx.segments else "本次回合结束无 HP 变化"
        )
        narrative = ctx.narrative
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"TurnEndArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 仲裁者是所在场景（stage），与出牌仲裁一致：结果写入 stage 记忆。
        # agent_loop 已原地写入完整提示词与工具调用轨迹，这里仅补记干净的结构化结果。
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=AIMessage(
                content=json.dumps(
                    {
                        "combat_log": combat_log,
                        "narrative": narrative,
                        "unsettled_affixes": ctx.unsettled_affixes,
                    },
                    ensure_ascii=False,
                )
            ),
        )

        # 全场景广播（与出牌仲裁一致）：除受影响角色外，持有者与旁观者也需知道回合结束
        # 发生了什么——持有者自身 HP 未必变化（如只伤害对手的词缀）。
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=_build_turn_end_arbitration_broadcast(
                    combat_log,
                    narrative,
                    current_round_number,
                    holder.name,
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
                f"[TurnEndArbitrationSystem] 词缀无法按计算规则结算（telemetry）: {affix}"
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
