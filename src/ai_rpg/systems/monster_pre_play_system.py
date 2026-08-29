from typing import Dict, Final, List, final, override

from loguru import logger
from pydantic import BaseModel

from ..deepseek import DeepSeekClient, batch_chat
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_stats,
    get_alive_actors_in_stage,
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
    PartyMemberComponent,
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
def _target_label(card: Card) -> str:
    """返回卡牌目标约束的中文描述。"""
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
def _format_card(card: Card) -> str:
    """将一张手牌格式化为紧凑、信息密度高的文本。"""
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
def _build_context_block(
    monster_name: str,
    stats: CharacterStats,
    energy: int,
    hand_cards: List[Card],
    opponent_names: List[str],
    action_order: List[str],
    completed_actors: List[str],
) -> str:
    """构建出牌决策提示词共享的上下文块（状态/序列/手牌/对手）。"""
    self_info = (
        f"HP {stats.hp}/{stats.max_hp} | 攻击 {stats.attack} | "
        f"防御 {stats.defense} | 能量 {energy}"
    )
    cards_lines = "\n".join(_format_card(c) for c in hand_cards)
    opponents_lines = (
        "\n".join(f"- {name}" for name in opponent_names)
        if opponent_names
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
    opponent_names: List[str],
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
        opponent_names=opponent_names,
        action_order=action_order,
        completed_actors=completed_actors,
    )
    playable_names = [c.name for c in hand_cards if c.playable]
    card_names_json = "、".join(f'"{name}"' for name in playable_names)

    return f"""# 第 {current_round_number} 回合 · 出牌决策

请从「手牌」中选择一张打出，或跳过本回合（pass_turn=true）。只返回 JSON。

{context}

## 决策规则

- 行动按序列顺序执行，排在你前面的角色已行动，其目标可能已死亡。
- 只能打出「可出」的牌；「不可出」（playable=False）的牌只能留在手牌中，不要选择。
- targets 从「存活对手」中选全名；目标为「自身」的牌可省略 targets。
- SINGLE 填恰好 1 个目标；ALL/SPREAD 填恰好 1 个阵营锚点，系统自动展开为对应阵营的存活角色。
- 若没有可执行的牌，返回 pass_turn=true，card_name/targets 可省略。

## 输出 JSON

```json
{{
  "pass_turn": false,
  "card_name": "选择的手牌名（可出：{card_names_json}）",
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
    opponent_names: List[str],
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
        opponent_names=opponent_names,
        action_order=action_order,
        completed_actors=completed_actors,
    )
    playable_names = [c.name for c in hand_cards if c.playable]
    card_names_json = "、".join(f'"{name}"' for name in playable_names)

    return f"""# 第 {current_round_number} 回合 · 出牌决策

{context}

输出 JSON（pass_turn/card_name/targets；可出卡牌：{card_names_json}）"""


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

        # 获取场上存活的远征队成员名称（对手，不传入血量）
        alive_actors = get_alive_actors_in_stage(self._game, entity)
        opponent_names: List[str] = [
            actor.name for actor in alive_actors if actor.has(PartyMemberComponent)
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
            opponent_names=opponent_names,
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
            opponent_names=opponent_names,
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
