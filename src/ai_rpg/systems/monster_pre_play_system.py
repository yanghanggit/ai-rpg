"""怪物出牌决策系统：怪物自己选牌选目标，决策过程只留「做了什么 + 原因」。"""

from typing import Dict, Final, List, Optional, final, override

from loguru import logger
from pydantic import BaseModel

from ..deepseek import DeepSeekClient, batch_chat
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_stats,
    get_alive_party_members_in_stage,
    get_energy,
    resolve_targets,
)
from ..game.dbg_game import DBGGame
from ..game.rpg_agent_memory import REPLACED_MESSAGES_ATTR
from ..llm import ChatClientProtocol
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
from ..utils import extract_json, prompt_builder
from .combat_decision_common import (
    ACTION_PASS,
    ACTION_PLAY,
    REASON_MISSING,
    build_combat_decision_record,
    build_combat_decision_tag,
)


#######################################################################################################################################
@final
class _MonsterDecisionResponse(BaseModel):
    """LLM 返回的怪物出牌决策"""

    pass_turn: bool = False
    card_name: str = ""
    targets: List[str] = []
    reason: str = ""  # 为什么这样打（或为什么过牌）


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
    """将一张手牌格式化为紧凑、信息密度高的文本（出牌决策提示词的文本片段）。"""
    lines = [
        f"- 【{card.name}】{card.description}",
        f"  费用{card.cost} 伤害{card.damage}×{card.hit_count}段 格挡{card.block} 目标:{_target_label(card)} {'可出' if card.playable else '不可出'}",
        render_labeled_str_list("  即时词缀", card.on_play_affixes, indent="    "),
        render_labeled_str_list("  受击词缀", card.on_hit_affixes, indent="    "),
        render_labeled_str_list(
            "  回合结束词缀", card.on_turn_end_affixes, indent="    "
        ),
        render_labeled_str_list(
            "  自主运行词缀", card.on_autonomous_affixes, indent="    "
        ),
    ]

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
    self_info = f"HP {stats.hp}/{stats.max_hp} | 速度 {stats.speed} | 剩余能量 {energy}（每打出一张牌需支付其「费用 cost」点能量）"
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
    position_text = f"第 {my_position} 位" if my_position is not None else "未知"
    completed_text = "、".join(completed_actors) if completed_actors else "无"

    return f"""## 你的状态

{self_info}

## 行动序列

完整序列：{order_display}
已行动：{completed_text}
你的位置：{position_text}，现在轮到你

## 手牌

{cards_lines}

## 存活对手

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
        card_names_hint = "无——剩余能量不足以支付任何牌，请返回 pass_turn=true"

    return f"""# 第 {current_round_number} 回合 · 出牌决策

请从「手牌」中选择一张打出，或跳过本回合（pass_turn=true）。只返回 JSON。

{context}

## 决策规则

- 行动按序列顺序执行，排在你前面的角色已行动，其目标可能已死亡。
- 只能打出「可出」的牌；「不可出」（playable=False）的牌只能留在手牌中，不要选择。
- 每打出一张牌需支付其「费用 cost」点能量；你当前剩余能量为 {energy}，只能选择 cost ≤ {energy} 的牌。
- 若所有「可出」牌的 cost 都大于剩余能量，则必须返回 pass_turn=true。
- targets 从「存活对手」中选全名；目标为「自身」的牌可省略 targets。
- 「存活对手」的「总格挡」为该对手手牌 block 之和（持有即生效），「手牌 N 张」为其当前手牌总数；「向你亮出的手牌」为带受击词缀的牌或来源你的牌——带受击词缀的牌会在你命中该对手时触发，可据此权衡命中收益与反噬风险。
- SINGLE 填恰好 1 个目标；ALL/SPREAD 填恰好 1 个阵营锚点，系统自动展开为对应阵营的存活角色。
- 若没有可执行的牌，返回 pass_turn=true，card_name/targets 可省略。
- reason（必填）：一句话说明**为什么这样打 / 为什么过牌**（40 字以内，给出你自己的判断依据即可）。

## 输出 JSON

```json
{{
  "pass_turn": false,
  "card_name": "选择的手牌名（可出：{card_names_hint}）",
  "targets": ["目标全名列表；目标为自身时可为 []]"],
  "reason": "为什么这样打 / 为什么过牌（一句话）"
}}
```"""


#######################################################################################################################################
@final
class _DecisionOutcome:
    """一次决策的收敛结果：打哪张 / 打谁；``card is None`` 即过牌。"""

    def __init__(
        self,
        *,
        card: Optional[Card] = None,
        intended_card: Optional[Card] = None,
        targets: Optional[List[str]] = None,
        reason: str = "",
        forced_cause: str = "",
    ) -> None:
        # card：实际打出的牌（None = 过牌）；intended_card：被拦下时「本想打哪张」
        self.card = card
        self.intended_card = intended_card or card
        self.targets: List[str] = targets or []
        self.reason = reason
        self.forced_cause = forced_cause

    @property
    def card_name(self) -> str:
        """被系统拦下时也要写进记录（说明「本想打哪张」）。"""
        return self.intended_card.name if self.intended_card is not None else ""

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
class MonsterPrePlaySystem(ReactiveProcessor):
    """
    怪物出牌决策系统。
    """

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

        # 验证战斗状态
        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("MonsterPrePlaySystem: 战斗未进行中，跳过决策")
            return

        logger.debug(f"MonsterPrePlaySystem: 为 {len(entities)} 个怪物进行出牌决策推理")

        # 为每个怪物创建推理 client（构造仍绑定 DeepSeek，使用侧只看协议）
        chat_clients: List[ChatClientProtocol] = [
            self._create_monster_decision_client(entity) for entity in entities
        ]

        if not chat_clients:
            logger.warning("MonsterPrePlaySystem: 没有可推理的怪物实体，跳过")
            return

        # 并行 LLM 推理
        await batch_chat(clients=chat_clients)

        # 解析并替换 PlayCardsAction
        for client in chat_clients:
            # 解析 LLM 响应，替换 PlayCardsAction
            self._process_monster_decision(client)

    ####################################################################################################################################
    def _create_monster_decision_client(self, entity: Entity) -> DeepSeekClient:
        """为单个怪物实体创建出牌决策的 DeepSeekClient。"""
        assert entity.has(
            HandComponent
        ), f"MonsterPrePlaySystem: 怪物 {entity.name} 缺少 HandComponent"
        hand_comp = entity.get(HandComponent)
        assert hand_comp is not None, f"MonsterPrePlaySystem: HandComponent 不能为空"

        # 计算怪物的当前战斗属性
        monster_stats = compute_character_stats(entity)
        energy = get_energy(entity)

        # 获取场上存活的队伍成员（对手），构建决策视角快照（HP / 总格挡 / 来源本怪物的受击牌）
        alive_party_members = get_alive_party_members_in_stage(entity, self._game)
        opponents: List[_OpponentView] = [
            _build_opponent_view(actor, monster_name=entity.name)
            for actor in alive_party_members
        ]

        # 获取本回合行动顺序信息
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        action_order: List[str] = latest_round.action_order if latest_round else []
        completed_actors: List[str] = (
            latest_round.completed_actors if latest_round else []
        )

        # 获取当前回合数（用于提示信息）
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 构建怪物出牌决策的提示信息（Prompt）
        prompt = _build_monster_decision_prompt(
            monster_name=entity.name,
            monster_stats=monster_stats,
            energy=energy,
            hand_cards=hand_comp.cards,
            opponents=opponents,
            action_order=action_order,
            completed_actors=completed_actors,
            current_round_number=current_round_number,
        )

        return DeepSeekClient(
            label=entity.name,
            input_message=prompt,
            messages=self._game.get_agent_memory(entity).messages,
        )

    ####################################################################################################################################
    def _process_monster_decision(self, client: ChatClientProtocol) -> None:
        """解析决策回包，落一条决策记录，再替换成 PlayCardsAction / PassTurnAction。

        记忆形状：先按「环境+任务提示词 → 模型回包」写入（审计可查），随后整段替换成
        一条人类可读的决策记录（做了什么 + 原因）；原文通过 `replaced_messages` 留在存档。
        """

        entity = self._game.get_entity_by_name(client.label)
        assert entity is not None, f"MonsterPrePlaySystem: 无法找到实体 {client.label}"

        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 先记录原始决策过程（被替换的原文通过 dump_attr 留在存档里）
        start_index = len(self._game.get_agent_memory(entity).messages)
        self._game.add_human_message(
            entity=entity,
            human_message=HumanMessage(
                content=client.input_message,
                draw_cards_round_number=current_round_number,
            ),
        )
        if client.response_ai_message is not None:
            self._game.add_ai_message(entity, client.response_ai_message)

        outcome = self._decide(entity, client)
        self._write_decision_record(
            entity,
            start_index=start_index,
            round_number=current_round_number,
            outcome=outcome,
        )

        # 落库：出牌或过牌
        if outcome.card is None:
            entity.replace(PassTurnAction, entity.name)
            logger.debug(
                f"MonsterPrePlaySystem: [{entity.name}] 决策过牌（{outcome.forced_cause or '主动跳过本次出牌机会'}）"
            )
            return

        entity.replace(PlayCardsAction, entity.name, outcome.card, outcome.targets)
        logger.debug(
            f"MonsterPrePlaySystem: [{entity.name}] 决策出牌 '{outcome.card.name}'，目标：{outcome.targets}"
        )

    ####################################################################################################################################
    def _decide(self, entity: Entity, client: ChatClientProtocol) -> "_DecisionOutcome":
        """把回包翻译成「打哪张、打谁」；任何异常都收敛成带原因的过牌。"""

        reason = ""

        if client.response_ai_message is None:
            logger.error(
                f"MonsterPrePlaySystem: [{entity.name}] LLM 返回空响应，执行过牌"
            )
            return _DecisionOutcome(forced_cause="决策没有返回任何内容", reason=reason)

        try:
            decision = _MonsterDecisionResponse.model_validate_json(
                extract_json(client.response_content)
            )
        except Exception as e:
            logger.error(f"{client.response_content}")
            logger.error(
                f"MonsterPrePlaySystem: [{entity.name}] 解析 LLM 响应失败，执行过牌。Exception: {e}"
            )
            return _DecisionOutcome(forced_cause="决策内容无法解析", reason=reason)

        reason = decision.reason.strip()

        if decision.pass_turn:
            return _DecisionOutcome(reason=reason)

        hand_comp = entity.get(HandComponent)
        assert hand_comp is not None, "MonsterPrePlaySystem: HandComponent 不能为空"

        selected_card = next(
            (c for c in hand_comp.cards if c.name == decision.card_name), None
        )
        if selected_card is None:
            logger.error(
                f"MonsterPrePlaySystem: [{entity.name}] LLM 返回的卡牌名 '{decision.card_name}' 不在手牌中：{[c.name for c in hand_comp.cards]}，执行过牌"
            )
            return _DecisionOutcome(
                forced_cause=f"「{decision.card_name}」不在你的手牌中",
                reason=reason,
            )

        # 兜底校验：不可出 / 能量不足都按过牌处理，绝不让错误决策进入结算
        if not selected_card.playable:
            logger.error(
                f"MonsterPrePlaySystem: [{entity.name}] 决策选出不可出牌的 '{selected_card.name}'，强制过牌"
            )
            return _DecisionOutcome(
                intended_card=selected_card,
                forced_cause="这张牌不可出牌",
                reason=reason,
            )

        energy = get_energy(entity)
        if energy < selected_card.cost:
            logger.warning(
                f"MonsterPrePlaySystem: [{entity.name}] 决策出牌 '{selected_card.name}' 能量不足（费用 {selected_card.cost} > 剩余 {energy}），强制过牌"
            )
            return _DecisionOutcome(
                intended_card=selected_card,
                forced_cause=(
                    f"当前剩余能量 {energy} 点不足以支付费用 {selected_card.cost}"
                ),
                reason=reason,
            )

        valid_targets, resolve_err = resolve_targets(
            selected_card.target_type,
            selected_card.hit_count,
            entity,
            decision.targets,
            self._game,
        )
        if resolve_err:
            logger.warning(
                f"MonsterPrePlaySystem: [{entity.name}] 目标解析失败：{resolve_err}，执行过牌"
            )
            return _DecisionOutcome(
                intended_card=selected_card,
                forced_cause=f"目标无法确认（{resolve_err}）",
                reason=reason,
            )

        return _DecisionOutcome(
            card=selected_card, targets=valid_targets, reason=reason
        )

    ####################################################################################################################################
    def _write_decision_record(
        self,
        entity: Entity,
        *,
        start_index: int,
        round_number: int,
        outcome: "_DecisionOutcome",
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

    ####################################################################################################################################
