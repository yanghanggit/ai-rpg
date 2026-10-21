"""怪物出牌决策系统：用工具调用流让怪物自己选牌选目标，只留「做了什么 + 原因」。

`submit_decision` 是唯一提交方式（非法提交由工具回错，模型在同一段 loop 内自纠）；
loop 后整段过程被替换成一条决策记录（形状与 `PartyCombatDecisionSystem` 一致），
没提交出可执行结果时兜底过牌。设计取舍见 docs/wiki/combat-pipeline.md。
"""

from functools import partial
from typing import Dict, Final, List, Optional, final, override

from loguru import logger
from pydantic import BaseModel

from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_stats,
    get_alive_party_members_in_stage,
    get_energy,
    resolve_targets,
)
from ..game.dbg_game import DBGGame
from ..game.rpg_agent_memory import REPLACED_MESSAGES_ATTR
from ..llm import ToolDefinition, ToolFunction
from ..models import (
    Card,
    CharacterStats,
    DeathComponent,
    HandComponent,
    HumanMessage,
    MonsterComponent,
    MonsterTurnAction,
    PassTurnAction,
    PlayCardsAction,
    TargetType,
    render_labeled_str_list,
)
from ..utils import prompt_builder
from .arbitration_common import make_loop_id
from .card_pile_common import (
    READ_PILES_TOOL,
    READ_PILES_TOOL_NAME,
    handle_read_piles,
)
from .combat_decision_common import (
    ACTION_PASS,
    ACTION_PLAY,
    REASON_MISSING,
    build_combat_decision_record,
    build_combat_decision_tag,
    format_targets,
    play_blocked_cause,
)

#######################################################################################################################################
# 单次决策 loop 的轮次上限：首轮提交 + 若干次「被工具回错后改正」的机会。
MAX_DECISION_ROUNDS: Final[int] = 4

#######################################################################################################################################
# 决策 loop 的 kind（拼进 loop_id，供存档记忆里反查本次决策过程）。
LOOP_KIND: Final[str] = "monster_decision"


#######################################################################################################################################
@final
class _OpponentView(BaseModel):
    """怪物出牌决策视角下的单个对手快照。"""

    name: str
    hp: int
    max_hp: int
    total_block: int  # 手牌 block 之和（持有即生效的总格挡）
    hand_count: int  # 手牌总数（模糊概念，只亮出「带受击词缀 或 来源本怪物」的牌）
    revealed_cards: List[Card]  # 手牌中「带受击词缀，或来源为本怪物」的卡牌


#######################################################################################################################################
# 「提交出牌决策」工具：本回合唯一的提交方式（terminal tool）。
SUBMIT_DECISION_TOOL_NAME: Final[str] = "submit_decision"

SUBMIT_DECISION_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name=SUBMIT_DECISION_TOOL_NAME,
        description="提交本回合的出牌决策（打出某张手牌，或过牌）。这是本回合唯一的提交方式：提交不合法时会收到错误说明，请按提示改正后重新调用；不要用普通文本作答。",
        parameters={
            "type": "object",
            "properties": {
                "pass_turn": {
                    "type": "boolean",
                    "description": "true=本回合不出牌（过牌）；false=打出手牌中的一张牌",
                },
                "card_name": {
                    "type": "string",
                    "description": "要打出的手牌名（pass_turn=false 时必填，须与手牌中的名字完全一致）",
                },
                "targets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "目标角色全名列表（从「存活对手」中选）；目标为「自身」的牌留空",
                },
                "reason": {
                    "type": "string",
                    "description": "一句话说明为什么这样打 / 为什么过牌（40 字以内，写你自己的判断依据）",
                },
            },
            "required": ["pass_turn", "reason"],
        },
    )
)


#######################################################################################################################################
# 工具序列：`read_piles`（非终止，可任意轮调用）→ `submit_decision`（终止）。
#######################################################################################################################################
@prompt_builder
def _target_label(card: Card) -> str:
    """返回卡牌目标约束的中文描述（出牌决策提示词的文本片段）。"""
    match card.target_type:
        case TargetType.SELF:
            return "自身"
        case TargetType.SINGLE:
            return "单个目标"
        case TargetType.ALL:
            return "阵营全体(锚点)"
        case TargetType.SPREAD:
            return "阵营散射(锚点)"
    return str(card.target_type.value)


#######################################################################################################################################
@prompt_builder
def _format_card(card: Card) -> str:
    """将一张手牌格式化为紧凑文本（空词缀不渲染）。"""
    lines = [
        (
            f"- 【{card.name}】{card.description}"
            if card.description
            else f"- 【{card.name}】"
        ),
        f"  费用{card.cost} 伤害{card.damage}×{card.hit_count}段 格挡{card.block} 目标:{_target_label(card)} {'可出' if card.playable else '不可出'}",
    ]
    for label, affixes in (
        ("即时词缀", card.on_play_affixes),
        ("受击词缀", card.on_hit_affixes),
        ("回合结束词缀", card.on_turn_end_affixes),
        ("自主运行词缀", card.on_autonomous_affixes),
    ):
        if affixes:
            lines.append(render_labeled_str_list(f"  {label}", affixes, indent="    "))

    flags = []
    if card.exhaust:
        flags.append("消耗")
    if card.retain:
        flags.append("保留")
    if card.ethereal:
        flags.append("虚无")
    if flags:
        lines.append("  特性:" + "、".join(flags))

    return "\n".join(lines)


#######################################################################################################################################
@prompt_builder
def _format_revealed_opponent_card(card: Card, monster_name: str) -> str:
    """格式化对手手牌中向怪物亮出的卡牌（带受击词缀，或来源为本怪物）。"""
    lines = [f"    - 【{card.name}】{card.description}"]
    if card.on_hit_affixes:
        lines.append(
            render_labeled_str_list(
                "      受击词缀", card.on_hit_affixes, indent="        "
            )
        )
    if card.source == monster_name:
        lines.append("      来源你")
    return "\n".join(lines)


#######################################################################################################################################
@prompt_builder
def _format_opponent(view: _OpponentView, monster_name: str) -> str:
    """格式化单个对手：HP / 总格挡 / 手牌总数，以及向怪物亮出的手牌。"""
    lines = [
        f"- {view.name}：HP {view.hp}/{view.max_hp} | 总格挡 {view.total_block} | 手牌 {view.hand_count} 张"
    ]
    if view.revealed_cards:
        lines.append("  向你亮出的手牌（带受击词缀，或来源为你）：")
        lines.extend(
            _format_revealed_opponent_card(c, monster_name) for c in view.revealed_cards
        )
    return "\n".join(lines)


#######################################################################################################################################
def _build_opponent_view(opponent: Entity, monster_name: str) -> _OpponentView:
    """为单个对手构建决策视角快照（HP / 总格挡 / 手牌总数 / 亮出的手牌）。"""
    stats = compute_character_stats(opponent)
    hand = opponent.get(HandComponent) if opponent.has(HandComponent) else None
    hand_cards = hand.cards if hand is not None else []
    total_block = sum(c.block for c in hand_cards)
    revealed_cards = [
        c for c in hand_cards if c.on_hit_affixes or c.source == monster_name
    ]
    return _OpponentView(
        name=opponent.name,
        hp=stats.hp,
        max_hp=stats.max_hp,
        total_block=total_block,
        hand_count=len(hand_cards),
        revealed_cards=revealed_cards,
    )


#######################################################################################################################################
def _affordable_playable_names(hand_cards: List[Card], energy: int) -> List[str]:
    """返回手牌中「可出且费用可支付（cost <= 剩余能量）」的卡牌名列表。"""
    return [c.name for c in hand_cards if c.playable and c.cost <= energy]


#######################################################################################################################################
def _card_names(hand_cards: List[Card]) -> str:
    """把一手牌压成「名（费用）、…」的清单，供工具回错时点名可选范围。"""
    return "、".join(f"{c.name}（费用{c.cost}）" for c in hand_cards) or "无"


#######################################################################################################################################
@prompt_builder
def _build_context_block(
    monster_name: str,
    stats: CharacterStats,
    energy: int,
    hand_cards: List[Card],
    opponents: List[_OpponentView],
    action_order: List[str],
    completed_actors: List[str],
) -> str:
    """构建出牌决策提示词共享的上下文块（状态/序列/手牌/对手）。"""
    self_info = f"HP {stats.hp}/{stats.max_hp} | 速度 {stats.speed} | 剩余能量 {energy}（打出一张牌扣其「费用」，不足则打不出）"
    cards_lines = "\n".join(_format_card(c) for c in hand_cards)
    opponents_lines = (
        "\n".join(_format_opponent(o, monster_name) for o in opponents)
        if opponents
        else "- 无存活对手"
    )

    order_display = " → ".join(
        f"你（{name}）" if name == monster_name else name for name in action_order
    )
    my_position = next(
        (i + 1 for i, name in enumerate(action_order) if name == monster_name), None
    )
    position_text = f"你在第 {my_position} 位" if my_position is not None else "轮到你"
    completed_text = "、".join(completed_actors) if completed_actors else "无"

    return f"""## 你的状态

{self_info}

## 行动序列

{order_display}｜已行动：{completed_text}｜{position_text}，现在轮到你

## 手牌

{cards_lines}

## 存活对手（总格挡 = 该对手手牌 block 之和，持有即生效；「向你亮出的手牌」会在你命中时触发其受击词缀）

{opponents_lines}"""


#######################################################################################################################################
@prompt_builder
def _build_monster_decision_prompt(
    monster_name: str,
    monster_stats: CharacterStats,
    energy: int,
    hand_cards: List[Card],
    opponents: List[_OpponentView],
    action_order: List[str],
    completed_actors: List[str],
    current_round_number: int,
) -> str:
    """生成怪物出牌决策的 LLM 提示词（完整版）。"""

    context = _build_context_block(
        monster_name=monster_name,
        stats=monster_stats,
        energy=energy,
        hand_cards=hand_cards,
        opponents=opponents,
        action_order=action_order,
        completed_actors=completed_actors,
    )

    affordable_names = _affordable_playable_names(hand_cards, energy)
    if affordable_names:
        card_names_hint = "、".join(f'"{name}"' for name in affordable_names)
    else:
        card_names_hint = "无——剩余能量不足以支付任何牌，请提交 pass_turn=true"

    return f"""# 第 {current_round_number} 回合 · 出牌决策

用 `submit_decision` 打出「手牌」中的一张，或过掉本回合。

{context}

## 规则

- 目标：单个目标填 1 个全名；阵营全体 / 散射填 1 个锚点（系统自动展开）；自身可留空。
- 本回合可出的牌（费用 ≤ {energy}）：{card_names_hint}"""


#######################################################################################################################################
@final
class _DecisionOutcome:
    """一次决策的收敛结果：打哪张 / 打谁；``card is None`` 即过牌。"""

    def __init__(
        self,
        *,
        card: Optional[Card] = None,
        intended_card: Optional[Card] = None,
        intended_card_name: str = "",
        targets: Optional[List[str]] = None,
        reason: str = "",
        forced_cause: str = "",
    ) -> None:
        # card：实际打出的牌（None = 过牌）；intended_card / intended_card_name：被拦下时「本想打哪张」
        self.card = card
        self.intended_card = intended_card or card
        self.intended_card_name = intended_card_name
        self.targets: List[str] = targets or []
        self.reason = reason
        self.forced_cause = forced_cause

    @property
    def card_name(self) -> str:
        """被系统拦下时也要写进记录（说明「本想打哪张」）。"""
        if self.intended_card is not None:
            return self.intended_card.name
        return self.intended_card_name

    @property
    def forced(self) -> bool:
        """过牌并非出自模型本意（被系统拦下或决策不可用）。"""
        return bool(self.forced_cause)

    @property
    def effective_reason(self) -> str:
        """记录里的原因：模型没给就写占位句，不空着。"""
        return self.reason or REASON_MISSING


#######################################################################################################################################
@final
class _DecisionContext:
    """一次决策 loop 的收敛槽：工具写结论、系统读结论。

    ``blocked_card`` / ``blocked_cause`` 是最近一次被工具回错的尝试，供未收敛时兜底。
    """

    def __init__(self, start_index: int) -> None:
        self.start_index = start_index
        self.outcome: Optional[_DecisionOutcome] = None
        self.blocked_card: Optional[Card] = None
        self.blocked_card_name: str = ""
        self.blocked_cause: str = ""
        self.loop_ok: bool = False


#######################################################################################################################################
def _handle_submit_decision(
    game: DBGGame,
    entity: Entity,
    ctx: _DecisionContext,
    pass_turn: bool,
    reason: str = "",
    card_name: str = "",
    targets: Optional[List[str]] = None,
) -> str:
    """「提交出牌决策」工具：不合法的提交只回错、不落结论，让模型在同一段 loop 里改正。"""
    reason = (reason or "").strip()

    if pass_turn:
        ctx.outcome = _DecisionOutcome(reason=reason)
        return "已提交：本回合不出牌（过牌），立即生效。"

    hand_cards = entity.get(HandComponent).cards
    selected_card = next((c for c in hand_cards if c.name == card_name), None)
    if selected_card is None:
        ctx.blocked_card = None
        ctx.blocked_card_name = card_name
        ctx.blocked_cause = "它不在你的手牌中"
        return f"错误：「{card_name}」不在你的手牌中。你的手牌：{_card_names(hand_cards)}。请重新选择，或提交 pass_turn=true。"

    # 兜底校验：不可出 / 能量不足 / 目标无法确认都不进入结算，且原因回传给模型自纠
    blocked_cause = play_blocked_cause(selected_card)
    if blocked_cause:
        ctx.blocked_card, ctx.blocked_cause = selected_card, blocked_cause
        return f"错误：「{selected_card.name}」{blocked_cause}（playable=False），只能留在手牌中。请换一张，或提交 pass_turn=true。"

    energy = get_energy(entity)
    if energy < selected_card.cost:
        ctx.blocked_card = selected_card
        ctx.blocked_cause = (
            f"当前剩余能量 {energy} 点不足以支付费用 {selected_card.cost}"
        )
        return f"错误：{ctx.blocked_cause}。请换一张费用 ≤ {energy} 的牌，或提交 pass_turn=true。"

    valid_targets, resolve_err = resolve_targets(
        selected_card.target_type,
        selected_card.hit_count,
        entity,
        list(targets or []),
        game,
    )

    if resolve_err:
        ctx.blocked_card = selected_card
        ctx.blocked_cause = f"目标无法确认（{resolve_err}）"
        return f"错误：{ctx.blocked_cause}。请按「存活对手」中的全名重新提交，或提交 pass_turn=true。"

    ctx.outcome = _DecisionOutcome(
        card=selected_card, targets=valid_targets, reason=reason
    )
    return f"已提交：打出「{selected_card.name}」，目标：{format_targets(valid_targets) or '无'}。"


#######################################################################################################################################
@final
class MonsterCombatDecisionSystem(ReactiveProcessor):
    """怪物出牌决策系统：工具化决策，落库后整段过程压缩成一条决策记录。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {
            Matcher(MonsterTurnAction): GroupEvent.ADDED,
        }

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理怪物实体且未死亡的情况"""
        return (
            entity.has(MonsterTurnAction)
            and entity.has(HandComponent)
            and entity.has(MonsterComponent)
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("MonsterCombatDecisionSystem: 战斗未进行中，跳过决策")
            return

        logger.debug(
            f"MonsterCombatDecisionSystem: 为 {len(entities)} 个怪物进行出牌决策推理"
        )

        round_number = len(self._game.current_dungeon_combat_room.combat.rounds or [])

        # 行动权由 `Round.current_actor` 唯一决定，决策天然串行：一个怪物一段 loop + 一次落库。
        # 不并发（并发会让同一回合的多个决策互相看不见对方的结算结果），也不做批量提交。
        for entity in entities:
            ctx = _DecisionContext(len(self._game.get_agent_memory(entity).messages))
            await self._run_decision(entity, ctx, round_number)
            self._apply_decision(entity, ctx, round_number)

    ####################################################################################################################################
    async def _run_decision(
        self, entity: Entity, ctx: _DecisionContext, round_number: int
    ) -> None:
        """驱动单个怪物的工具化出牌决策（原地写记忆，事后整段压缩成一条记录）。"""
        memory = self._game.get_agent_memory(entity)
        loop_id = make_loop_id(memory.messages, LOOP_KIND, round_number, entity.name)

        try:

            result = await agent_loop(
                name=entity.name,
                input_message=self._build_decision_prompt(entity, round_number),
                # 原地写：工具轨迹先如实进记忆，落库阶段再整段替换成决策记录
                messages=memory.messages,
                tools=[READ_PILES_TOOL, SUBMIT_DECISION_TOOL],
                handlers={
                    READ_PILES_TOOL_NAME: partial(handle_read_piles, entity),
                    SUBMIT_DECISION_TOOL_NAME: partial(
                        _handle_submit_decision, self._game, entity, ctx
                    ),
                },
                terminal_tools=[SUBMIT_DECISION_TOOL],
                tool_choice="required",
                max_rounds=MAX_DECISION_ROUNDS,
                input_metadata={"draw_cards_round_number": round_number},
                loop_id=loop_id,
            )

            ctx.loop_ok = bool(result)

        except Exception as e:

            logger.error(
                f"MonsterCombatDecisionSystem: [{entity.name}] 决策 loop 异常: {e}"
            )
            ctx.loop_ok = False

        # agent_loop 直接原地追加 AI 消息（绕过 add_ai_message），需手动同步最新上下文占比
        self._game.sync_latest_context_usage_ratio(entity)

    ####################################################################################################################################
    def _build_decision_prompt(self, entity: Entity, round_number: int) -> str:
        """为单个怪物实体构建出牌决策提示词。"""
        assert entity.has(
            HandComponent
        ), f"MonsterCombatDecisionSystem: 怪物 {entity.name} 缺少 HandComponent"
        hand_comp = entity.get(HandComponent)
        assert (
            hand_comp is not None
        ), f"MonsterCombatDecisionSystem: HandComponent 不能为空"

        # 获取场上存活的队伍成员（对手），构建决策视角快照（HP / 总格挡 / 来源本怪物的受击牌）
        opponents: List[_OpponentView] = [
            _build_opponent_view(actor, monster_name=entity.name)
            for actor in get_alive_party_members_in_stage(entity, self._game)
        ]

        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        action_order: List[str] = latest_round.action_order if latest_round else []
        completed_actors: List[str] = (
            latest_round.completed_actors if latest_round else []
        )

        return _build_monster_decision_prompt(
            monster_name=entity.name,
            monster_stats=compute_character_stats(entity),
            energy=get_energy(entity),
            hand_cards=hand_comp.cards,
            opponents=opponents,
            action_order=action_order,
            completed_actors=completed_actors,
            current_round_number=round_number,
        )

    ####################################################################################################################################
    def _apply_decision(
        self, entity: Entity, ctx: _DecisionContext, round_number: int
    ) -> None:
        """落库：先把整段决策过程替换成一条记录，再替换成 PlayCardsAction / PassTurnAction。"""
        outcome = ctx.outcome
        if outcome is None:
            # 没在轮次上限内提交出可执行结论：按「本想打 X 但没打成」的过牌兜底
            outcome = _DecisionOutcome(
                intended_card=ctx.blocked_card,
                intended_card_name=ctx.blocked_card_name,
                forced_cause=ctx.blocked_cause or "决策没有返回可执行的结果",
            )
            logger.error(
                f"MonsterCombatDecisionSystem: [{entity.name}] 决策未收敛（loop_ok={ctx.loop_ok}），兜底过牌：{outcome.forced_cause}"
            )

        self._write_decision_record(
            entity,
            start_index=ctx.start_index,
            round_number=round_number,
            outcome=outcome,
        )

        if outcome.card is None:
            entity.replace(PassTurnAction, entity.name)
            logger.debug(
                f"MonsterCombatDecisionSystem: [{entity.name}] 决策过牌（{outcome.forced_cause or '主动跳过本次出牌机会'}）"
            )
            return

        entity.replace(PlayCardsAction, entity.name, outcome.card, outcome.targets)
        logger.debug(
            f"MonsterCombatDecisionSystem: [{entity.name}] 决策出牌 '{outcome.card.name}'，目标：{outcome.targets}"
        )

    ####################################################################################################################################
    def _write_decision_record(
        self,
        entity: Entity,
        *,
        start_index: int,
        round_number: int,
        outcome: _DecisionOutcome,
    ) -> None:
        """把「原始决策过程」整段替换为一条决策记录（做了什么 + 原因）。"""
        messages = self._game.get_agent_memory(entity).messages
        if outcome.card is None:
            action = ACTION_PASS
            card_name = outcome.card_name
        else:
            action = ACTION_PLAY
            card_name = outcome.card.name

        self._game.replace_span(
            entity,
            start_index,
            len(messages),
            [
                HumanMessage(
                    content=build_combat_decision_record(
                        round_number,
                        action,
                        card_name=card_name,
                        targets=outcome.targets,
                        reason=outcome.effective_reason,
                        forced_cause=outcome.forced_cause,
                    ),
                    combat_decision=build_combat_decision_tag(
                        round_number,
                        action,
                        card_name=card_name,
                        targets=outcome.targets,
                        reason=outcome.effective_reason,
                        forced=outcome.forced,
                    ),
                )
            ],
            dump_attr=REPLACED_MESSAGES_ATTR,
        )
