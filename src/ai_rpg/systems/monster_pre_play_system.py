from typing import Dict, Final, List, final, override

from loguru import logger
from pydantic import BaseModel

from ..deepseek import DeepSeekClient, batch_chat
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_stats,
    get_alive_actors_in_stage,
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
@prompt_builder
def _build_monster_decision_prompt(
    monster_name: str,
    monster_stats: CharacterStats,
    hand_cards: List[Card],
    opponent_names: List[str],
    action_order: List[str],
    completed_actors: List[str],
    current_round_number: int,
) -> str:
    """生成怪物出牌决策的 LLM 提示词。"""
    stats = monster_stats
    self_info = (
        f"HP:{stats.hp}/{stats.max_hp} | 攻击:{stats.attack} | 防御:{stats.defense}"
    )

    cards_lines = "\n".join(
        f"- 【{c.name}】描述：{c.description}"
        + (
            f"  即时词缀：{'\u3001'.join(c.on_play_affixes)}"
            if c.on_play_affixes
            else ""
        )
        + f"  damage:{c.damage}  hit_count:{c.hit_count}  block:{c.block}  self_target:{c.self_target}  target_type:{c.target_type}"
        for c in hand_cards
    )

    opponents_lines = (
        "\n".join(f"- {name}" for name in opponent_names)
        if opponent_names
        else "- 无存活对手"
    )

    # 构造行动序列文本，标注自己的位置
    order_display = " → ".join(
        f"你（{name}）" if name == monster_name else name for name in action_order
    )
    my_position = next(
        (i + 1 for i, name in enumerate(action_order) if name == monster_name), None
    )
    position_text = f"第 {my_position} 位" if my_position is not None else "未知"
    completed_text = "、".join(completed_actors) if completed_actors else "无"

    card_names_json = ", ".join(f'"{c.name}"' for c in hand_cards)

    return f"""# 第 {current_round_number} 回合：选择你的出牌（以 JSON 格式返回）

请根据当前局势选择一张手牌并决定攻击目标。

## 你的当前状态

{self_info}

## 本回合行动序列

完整序列：{order_display}
已行动：{completed_text}
你的位置：{position_text}，现在轮到你

## 当前手牌

{cards_lines}

## 场上存活对手

{opponents_lines}

## 决策建议

- 行动序列严格顺序执行，排在你前面的角色已出手，其目标可能已死亡
- targets 从"场上存活对手"中选全名；self_target 为 true 时可省略 targets；其余类型（SINGLE/ALL/SPREAD）须提供恰好 1 个目标全名：SINGLE 时即为该目标本身，ALL/SPREAD 时该目标作为阵营锚点，系统会自动展开为其所在阵营的全部/散射角色
- 若所有手牌均无法执行（如全部封印），可选择跳过出牌（pass_turn: true），此时 card_name/targets 可省略

## 输出 JSON

```json
{{
  "pass_turn": false,
  "card_name": "从手牌中选择一张卡牌的名称（必须是以下之一：{card_names_json}）",
  "targets": ["目标全名列表，self_target 为 true 时可为 []，其余类型须恰好 1 个元素"]
}}
```
pass_turn 为 true 时表示跳过出牌，其他字段可省略"""


#######################################################################################################################################
@prompt_builder
def _build_condensed_monster_decision_prompt(
    monster_name: str,
    monster_stats: CharacterStats,
    hand_cards: List[Card],
    opponent_names: List[str],
    action_order: List[str],
    completed_actors: List[str],
    current_round_number: int,
) -> str:
    """生成怪物出牌决策的精简版提示词（写入对话历史，减少 token 消耗）。"""
    stats = monster_stats
    self_info = (
        f"HP:{stats.hp}/{stats.max_hp} | 攻击:{stats.attack} | 防御:{stats.defense}"
    )

    cards_lines = "\n".join(
        f"- 【{c.name}】描述：{c.description}"
        + (f"  即时词缀：{'、'.join(c.on_play_affixes)}" if c.on_play_affixes else "")
        + f"  damage:{c.damage}  hit_count:{c.hit_count}  block:{c.block}  self_target:{c.self_target}  target_type:{c.target_type}"
        for c in hand_cards
    )

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

    card_names_json = ", ".join(f'"{c.name}"' for c in hand_cards)

    return f"""# 第 {current_round_number} 回合：选择你的出牌（以 JSON 格式返回）

## 你的当前状态

{self_info}

## 本回合行动序列

完整序列：{order_display}
已行动：{completed_text}
你的位置：{position_text}，现在轮到你

## 当前手牌

{cards_lines}

## 场上存活对手

{opponents_lines}

输出 JSON（pass_turn/card_name/targets；可用卡牌：{card_names_json})"""


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
            hand_cards=hand_comp.cards,
            opponent_names=opponent_names,
            action_order=action_order,
            completed_actors=completed_actors,
            current_round_number=current_round_number,
        )

        return DeepSeekClient(
            name=entity.name,
            full_prompt=prompt,
            context=self._game.get_agent_context(entity).context,
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

        # 根据 target_type 解析出牌目标（与玩家出牌走同一套 resolve_targets 逻辑，避免重复实现）
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
            None,  # gear_item 由 PlayCardsActionSystem 组装填充
        )
        logger.debug(
            f"MonsterPrePlaySystem: [{entity.name}] 决策出牌 '{selected_card.name}'，目标：{valid_targets}"
        )

    ####################################################################################################################################
