from typing import Dict, Final, List, final, override

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
)
from ..utils import extract_json, prompt_builder


#######################################################################################################################################
@final
class _MonsterDecisionResponse(BaseModel):
    """LLM 返回的怪物出牌决策"""

    pass_turn: bool = False
    card_name: str = ""
    targets: List[str] = []


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
    if card.self_target:
        return "自身"
    match card.target_type:
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
        f"  费用{card.cost} 伤害{card.damage}×{card.hit_count}段 格挡{card.block} "
        f"目标:{_target_label(card)} {'可出' if card.playable else '不可出'}",
    ]

    affix_parts = [
        f"即时词缀:{'、'.join(card.on_play_affixes) if card.on_play_affixes else '无'}",
        f"受击词缀:{'、'.join(card.on_hit_affixes) if card.on_hit_affixes else '无'}",
        f"回合结束词缀:{'、'.join(card.on_turn_end_affixes) if card.on_turn_end_affixes else '无'}",
    ]

    flags = []
    if card.exhaust:
        flags.append("消耗")
    if card.retain:
        flags.append("保留")
    if card.ethereal:
        flags.append("虚无")
    if flags:
        affix_parts.append("特性:" + "、".join(flags))

    lines.append("  " + " | ".join(affix_parts))
    return "\n".join(lines)


#######################################################################################################################################
@prompt_builder
def _format_revealed_opponent_card(card: Card, monster_name: str) -> str:
    """格式化对手手牌中向怪物亮出的卡牌（带受击词缀，或来源为本怪物）。"""
    tags = []
    if card.on_hit_affixes:
        tags.append(f"受击词缀:{'、'.join(card.on_hit_affixes)}")
    if card.source == monster_name:
        tags.append("来源你")
    suffix = f"（{'；'.join(tags)}）" if tags else ""
    return f"- 【{card.name}】{card.description}{suffix}"


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
            "    " + _format_revealed_opponent_card(c, monster_name)
            for c in view.revealed_cards
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
    self_info = (
        f"HP {stats.hp}/{stats.max_hp} | 攻击 {stats.attack} | "
        f"防御 {stats.defense} | 剩余能量 {energy}（每打出一张牌需支付其「费用 cost」点能量）"
    )
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

## 输出 JSON

```json
{{
  "pass_turn": false,
  "card_name": "选择的手牌名（可出：{card_names_hint}）",
  "targets": ["目标全名列表；目标为自身时可为 []]"
}}
```"""


#######################################################################################################################################
@prompt_builder
def _build_condensed_monster_decision_prompt(
    monster_name: str,
    monster_stats: CharacterStats,
    energy: int,
    hand_cards: List[Card],
    opponents: List[_OpponentView],
    action_order: List[str],
    completed_actors: List[str],
    current_round_number: int,
) -> str:
    """生成怪物出牌决策的精简版提示词（写入对话历史，减少 token 消耗）。"""
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
        card_names_hint = "无（剩余能量不足，应 pass_turn=true）"

    return f"""# 第 {current_round_number} 回合 · 出牌决策

{context}

输出 JSON（pass_turn/card_name/targets；可出且费用可支付的卡牌：{card_names_hint}；只能选择 cost ≤ 剩余能量的牌，无牌可出则 pass_turn=true）"""


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

        # 为每个怪物创建推理 DeepSeekClient
        chat_clients: List[DeepSeekClient] = []
        for entity in entities:
            client = self._create_monster_decision_client(entity)
            chat_clients.append(client)

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

        # 构建怪物出牌决策的精简提示信息（Condensed Prompt）
        condensed_prompt = _build_condensed_monster_decision_prompt(
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
            name=entity.name,
            full_prompt=prompt,
            messages=self._game.get_agent_memory(entity).messages,
            condensed_prompt=condensed_prompt,
        )

    ####################################################################################################################################
    def _process_monster_decision(self, client: DeepSeekClient) -> None:
        """解析 LLM 决策响应，替换怪物的 PlayCardsAction。"""

        entity = self._game.get_entity_by_name(client.name)
        assert entity is not None, f"MonsterPrePlaySystem: 无法找到实体 {client.name}"

        # 检查 LLM 是否返回了有效的 AI 消息，如果没有则记录错误并执行过牌
        if client.response_ai_message is None:
            logger.error(
                f"MonsterPrePlaySystem: [{entity.name}] LLM 返回空响应，执行过牌"
            )
            entity.replace(PassTurnAction, entity.name)
            return

        try:
            decision = _MonsterDecisionResponse.model_validate_json(
                extract_json(client.response_content)
            )
        except Exception as e:
            logger.error(f"{client.response_content}")
            logger.error(
                f"MonsterPrePlaySystem: [{entity.name}] 解析 LLM 响应失败，执行过牌。Exception: {e}"
            )
            entity.replace(PassTurnAction, entity.name)
            return

        # 写对话历史（精简版 prompt + AI 原文，附挂全量 prompt 供检索）
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.add_human_message(
            entity=entity,
            human_message=HumanMessage(
                content=client.condensed_prompt,
                draw_cards_round_number=current_round_number,
                draw_cards_full_prompt=client.full_prompt,
            ),
        )

        # 写入 LLM 原文响应
        self._game.add_ai_message(entity, client.response_ai_message)

        # 根据 LLM 决策替换 PlayCardsAction 或 PassTurnAction
        if decision.pass_turn:
            entity.replace(PassTurnAction, entity.name)
            logger.debug(
                f"MonsterPrePlaySystem: [{entity.name}] 决策过牌（跳过本次出牌机会）"
            )
            return

        hand_comp = entity.get(HandComponent)
        assert hand_comp is not None, "MonsterPrePlaySystem: HandComponent 不能为空"

        # 根据 LLM 决策的 card_name 查找手牌
        selected_card = next(
            (c for c in hand_comp.cards if c.name == decision.card_name),
            None,
        )
        if selected_card is None:
            logger.error(
                f"MonsterPrePlaySystem: [{entity.name}] LLM 返回的卡牌名 '{decision.card_name}' "
                f"不在手牌中：{[c.name for c in hand_comp.cards]}，执行过牌"
            )
            entity.replace(PassTurnAction, entity.name)
            return

        # 兜底校验：能量不足以支付所选卡牌费用 → 写入警告提醒（写入怪物 agent memory）+ 强制过牌，
        # 防止下游 play_cards_action_system 的 consume_energy 因能量不足触发 AssertionError。
        energy = get_energy(entity)
        if energy < selected_card.cost:
            logger.warning(
                f"MonsterPrePlaySystem: [{entity.name}] 决策出牌 '{selected_card.name}' "
                f"能量不足（费用 {selected_card.cost} > 剩余 {energy}），强制过牌"
            )
            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=(
                        f"# 出牌决策无效提醒\n"
                        f"你选择了「{selected_card.name}」（费用 {selected_card.cost}），"
                        f"但当前剩余能量仅 {energy} 点，不足以支付费用，本次已强制跳过出牌。"
                        f"下次当剩余能量不足以支付任何牌时，请直接返回 pass_turn=true。"
                    )
                ),
            )
            entity.replace(PassTurnAction, entity.name)
            return

        # 根据 target_type 解析出牌目标（与玩家出牌走同一套 resolve_targets 逻辑，避免重复实现；self_target 卡牌无需目标名）
        valid_targets, resolve_err = resolve_targets(
            selected_card.target_type,
            selected_card.hit_count,
            entity,
            decision.targets,
            self._game,
            selected_card.self_target,
        )
        if resolve_err:
            logger.warning(
                f"MonsterPrePlaySystem: [{entity.name}] 目标解析失败：{resolve_err}，执行过牌"
            )
            entity.replace(PassTurnAction, entity.name)
            return

        # 替换 PlayCardsAction，填入真实卡牌和目标
        entity.replace(
            PlayCardsAction,
            entity.name,
            selected_card,
            valid_targets,
        )
        logger.debug(
            f"MonsterPrePlaySystem: [{entity.name}] 决策出牌 '{selected_card.name}'，目标：{valid_targets}"
        )

    ####################################################################################################################################
