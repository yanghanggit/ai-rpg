import random
from typing import Final, List, final, override, Dict
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import get_alive_actors_in_stage
from ..game.dbg_entity_ops import compute_character_stats
from ..models import (
    PlayCardsAction,
    MonsterTurnAction,
    PassTurnAction,
    HumanMessage,
    MonsterComponent,
    DeathComponent,
    HandComponent,
    CharacterStats,
    PartyMemberComponent,
    Card,
    TargetType,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class MonsterDecisionResponse(BaseModel):
    """LLM 返回的怪物出牌决策"""

    pass_turn: bool = False
    card_name: str = ""
    targets: List[str] = []


#######################################################################################################################################
def _generate_monster_decision_prompt(
    monster_name: str,
    monster_stats: CharacterStats,
    hand_cards: List[Card],
    opponent_names: List[str],
    action_order: List[str],
    completed_actors: List[str],
    current_round_number: int,
) -> str:
    """生成怪物出牌决策的 LLM 提示词。

    Args:
        monster_name: 怪物名称
        monster_stats: 怪物当前战斗属性
        hand_cards: 当前手牌列表
        opponent_names: 场上存活对手名称列表（不含血量）
        action_order: 本回合完整行动序列
        completed_actors: 已完成出牌的角色名称列表
        current_round_number: 当前回合数

    Returns:
        格式化的完整提示词
    """
    stats = monster_stats
    self_info = (
        f"HP:{stats.hp}/{stats.max_hp} | 攻击:{stats.attack} | 防御:{stats.defense}"
    )

    cards_lines = "\n".join(
        f"- 【{c.name}】描述：{c.description}"
        + (f"  延迟词缀：{'\u3001'.join(c.affixes)}" if c.affixes else "")
        + (f"  即时词缀：{'\u3001'.join(c.modifiers)}" if c.modifiers else "")
        + f"  damage_dealt:{c.damage_dealt}  energy_delta:{c.energy_delta}  hit_count:{c.hit_count}  target_type:{c.target_type}"
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
- targets 从"场上存活对手"中选全名，可多选，可为空列表
- 若所有手牌均无法执行（如全部封印），可选择跳过出牌（pass_turn: true），此时 card_name/targets 可省略

## 输出 JSON

```json
{{
  "pass_turn": false,
  "card_name": "从手牌中选择一张卡牌的名称（必须是以下之一：{card_names_json}）",
  "targets": ["目标全名列表，可为 []"]
}}
```
pass_turn 为 true 时表示跳过出牌，其他字段可省略"""


#######################################################################################################################################
def _generate_compressed_monster_decision_prompt(
    monster_name: str,
    monster_stats: CharacterStats,
    hand_cards: List[Card],
    opponent_names: List[str],
    action_order: List[str],
    completed_actors: List[str],
    current_round_number: int,
) -> str:
    """生成怪物出牌决策的压缩版提示词（写入对话历史，减少 token 消耗）。"""
    stats = monster_stats
    self_info = (
        f"HP:{stats.hp}/{stats.max_hp} | 攻击:{stats.attack} | 防御:{stats.defense}"
    )

    cards_lines = "\n".join(
        f"- 【{c.name}】描述：{c.description}"
        + (f"  延迟词缀：{'、'.join(c.affixes)}" if c.affixes else "")
        + (f"  即时词缀：{'、'.join(c.modifiers)}" if c.modifiers else "")
        + f"  damage_dealt:{c.damage_dealt}  energy_delta:{c.energy_delta}  hit_count:{c.hit_count}  target_type:{c.target_type}"
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
        if not self._game.current_combat_room.combat.is_ongoing:
            logger.debug("MonsterPrePlaySystem: 战斗未进行中，跳过决策")
            return

        logger.debug(f"MonsterPrePlaySystem: 为 {len(entities)} 个怪物进行出牌决策推理")

        # 注入 context 引导（仅第一回合，强制过牌）
        # current_round_number = len(self._game.current_dungeon.current_rounds or [])
        # self._mock_inject_pass_turn_context(entities, current_round_number)

        # 为每个怪物创建推理 DeepSeekClient
        chat_clients: List[DeepSeekClient] = []
        for entity in entities:
            client = self._create_monster_decision_client(entity)
            # if client is not None:
            chat_clients.append(client)

        if not chat_clients:
            logger.warning("MonsterPrePlaySystem: 没有可推理的怪物实体，跳过")
            return

        # 并行 LLM 推理
        await DeepSeekClient.batch_chat(clients=chat_clients)

        # 解析并替换 PlayCardsAction
        for client in chat_clients:
            # 解析 LLM 响应，替换 PlayCardsAction
            self._process_monster_decision(client)

    ####################################################################################################################################
    def _create_monster_decision_client(self, entity: Entity) -> DeepSeekClient:
        """为单个怪物实体创建出牌决策的 DeepSeekClient。

        Args:
            entity: 怪物实体

        Returns:
            DeepSeekClient，若缺少必要组件则返回 None
        """
        assert entity.has(
            HandComponent
        ), f"MonsterPrePlaySystem: 怪物 {entity.name} 缺少 HandComponent"
        hand_comp = entity.get(HandComponent)
        # if hand_comp is None or len(hand_comp.cards) == 0:
        #     logger.error(f"MonsterPrePlaySystem: 怪物 {entity.name} 没有手牌，无法决策")
        #     return None

        monster_stats = compute_character_stats(entity)

        # 获取场上存活的远征队成员名称（对手，不传入血量）
        alive_actors = get_alive_actors_in_stage(self._game, entity)
        opponent_names: List[str] = [
            actor.name for actor in alive_actors if actor.has(PartyMemberComponent)
        ]

        # 获取本回合行动顺序信息
        latest_round = self._game.current_combat_room.combat.latest_round
        action_order: List[str] = latest_round.action_order if latest_round else []
        completed_actors: List[str] = (
            latest_round.completed_actors if latest_round else []
        )

        current_round_number = len(self._game.current_combat_room.combat.rounds or [])

        prompt = _generate_monster_decision_prompt(
            monster_name=entity.name,
            monster_stats=monster_stats,
            hand_cards=hand_comp.cards,
            opponent_names=opponent_names,
            action_order=action_order,
            completed_actors=completed_actors,
            current_round_number=current_round_number,
        )

        compressed_prompt = _generate_compressed_monster_decision_prompt(
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
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
            compressed_prompt=compressed_prompt,
        )

    ####################################################################################################################################
    # def _mock_inject_pass_turn_context(
    #     self, entities: List[Entity], current_round_number: int
    # ) -> None:
    #     """[mock] 第一回合向怪物注入 context，强制引导 LLM 选择 pass_turn。"""
    #     if current_round_number != 1:
    #         return
    #     msg = (
    #         "[系统提示] 本回合你必须选择跳过出牌。"
    #         "请在 JSON 响应中将 pass_turn 设为 true，其余字段可省略。"
    #     )
    #     for entity in entities:
    #         self._game.add_human_message(entity, msg)
    #         logger.debug(f"[mock context] [{entity.name}] 注入 pass_turn 引导 context")

    ####################################################################################################################################
    def _process_monster_decision(self, client: DeepSeekClient) -> None:
        """解析 LLM 决策响应，替换怪物的 PlayCardsAction。

        Args:
            entity: 怪物实体
            client: 包含 LLM 响应的 DeepSeekClient
        """

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
            decision = MonsterDecisionResponse.model_validate_json(
                extract_json_from_code_block(client.response_content)
            )
        except Exception as e:
            logger.error(f"{client.response_content}")
            logger.error(
                f"MonsterPrePlaySystem: [{entity.name}] 解析 LLM 响应失败，执行过牌。Exception: {e}"
            )
            entity.replace(PassTurnAction, entity.name)
            return

        # 写对话历史（压缩版 prompt + AI 原文，附挂全量 prompt 供检索）
        current_round_number = len(self._game.current_combat_room.combat.rounds or [])
        self._game.add_human_message(
            entity=entity,
            human_message=HumanMessage(
                content=client.compressed_prompt,
                draw_cards_round_number=current_round_number,
                draw_cards_full_prompt=client.prompt,
            ),
        )
        assert (
            client.response_ai_message is not None
        ), "MonsterPrePlaySystem: AI 消息不能为空"
        self._game.add_ai_message(entity, client.response_ai_message)

        if decision.pass_turn:
            entity.replace(PassTurnAction, entity.name)
            logger.debug(
                f"MonsterPrePlaySystem: [{entity.name}] 决策过牌（跳过本次出牌机会）"
            )
            return

        hand_comp = entity.get(HandComponent)
        assert hand_comp is not None, "MonsterPrePlaySystem: HandComponent 不能为空"

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

        # 根据 target_type 解析出牌目标
        alive_actors = get_alive_actors_in_stage(self._game, entity)
        alive_names = {a.name for a in alive_actors}

        match selected_card.target_type:
            case TargetType.ENEMY_ALL:
                # 自动填充所有存活的远征队成员（对怪物来说"敌方"= PartyMember）
                valid_targets = [
                    a.name for a in alive_actors if a.has(PartyMemberComponent)
                ]
            case TargetType.ENEMY_RANDOM_MULTI:
                # 每段独立随机命中一名存活远征队成员（对怪物来说"敌方"= PartyMember）
                party_members = [a for a in alive_actors if a.has(PartyMemberComponent)]
                valid_targets = (
                    [
                        e.name
                        for e in random.choices(
                            party_members, k=selected_card.hit_count
                        )
                    ]
                    if party_members
                    else []
                )
            case TargetType.SELF_ONLY:
                # 仅作用于施法者自身
                valid_targets = [entity.name]
            case _:
                # ENEMY_SINGLE / ALLY_* — 过滤掉不存在的目标名
                valid_targets = [t for t in decision.targets if t in alive_names]
                if len(valid_targets) != len(decision.targets):
                    logger.warning(
                        f"MonsterPrePlaySystem: [{entity.name}] 过滤无效目标 "
                        f"{set(decision.targets) - alive_names}"
                    )

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
