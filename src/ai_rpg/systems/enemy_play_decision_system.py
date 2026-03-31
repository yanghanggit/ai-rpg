from typing import Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    PlayCardsAction,
    EnemyComponent,
    DeathComponent,
    HandComponent,
    CharacterStatsComponent,
    ExpeditionMemberComponent,
    Card,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class EnemyDecisionResponse(BaseModel):
    """LLM 返回的敌人出牌决策"""

    card_name: str
    targets: List[str]


#######################################################################################################################################
def _generate_enemy_decision_prompt(
    enemy_name: str,
    enemy_stats: CharacterStatsComponent,
    hand_cards: List[Card],
    opponent_names: List[str],
    action_order: List[str],
    completed_actors: List[str],
    current_round_number: int,
) -> str:
    """生成敌人出牌决策的 LLM 提示词。

    Args:
        enemy_name: 敌人名称
        enemy_stats: 敌人当前战斗属性
        hand_cards: 当前手牌列表
        opponent_names: 场上存活对手名称列表（不含血量）
        action_order: 本回合完整行动序列
        completed_actors: 已完成出牌的角色名称列表
        current_round_number: 当前回合数

    Returns:
        格式化的完整提示词
    """
    stats = enemy_stats.stats
    self_info = (
        f"HP:{stats.hp}/{stats.max_hp} | 攻击:{stats.attack} | 防御:{stats.defense}"
    )

    cards_lines = "\n".join(
        f"- 【{c.name}】行动：{c.action}  damage_dealt:{c.damage_dealt}  block_gain:{c.block_gain}"
        for c in hand_cards
    )

    opponents_lines = (
        "\n".join(f"- {name}" for name in opponent_names)
        if opponent_names
        else "- 无存活对手"
    )

    # 构造行动序列文本，标注自己的位置
    order_display = " → ".join(
        f"你（{name.split('.')[-1]}）" if name == enemy_name else name.split(".")[-1]
        for name in action_order
    )
    my_position = next(
        (i + 1 for i, name in enumerate(action_order) if name == enemy_name), None
    )
    position_text = f"第 {my_position} 位" if my_position is not None else "未知"
    completed_text = (
        "、".join(name.split(".")[-1] for name in completed_actors)
        if completed_actors
        else "无"
    )

    card_names_json = ", ".join(f'"{c.name}"' for c in hand_cards)

    return f"""# 第 {current_round_number} 回合：选择你的出牌（以 JSON 格式返回）

你是战场上的敌方角色 {enemy_name}，请根据当前局势选择一张手牌并决定攻击目标。

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

- 若你的 HP 较低，可考虑选用高 block_gain 的防御卡牌
- targets 必须从"场上存活对手"列表中选取全名，可选多个，可为空列表

## 输出 JSON

```json
{{
  "card_name": "从手牌中选择一张卡牌的名称（必须是以下之一：{card_names_json}）",
  "targets": ["目标全名列表，可为 []"]
}}
```"""


#######################################################################################################################################
@final
class EnemyPlayDecisionSystem(ReactiveProcessor):

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理敌人实体且未死亡的情况"""
        return (
            entity.has(PlayCardsAction)
            and entity.has(HandComponent)
            and entity.has(EnemyComponent)
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        # 验证战斗状态
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("EnemyDrawDecisionSystem: 战斗未进行中，跳过决策")
            return

        logger.debug(
            f"EnemyPlayDecisionSystem: 为 {len(entities)} 个敌人进行出牌决策推理"
        )

        # 为每个敌人创建推理 ChatClient
        chat_clients: List[ChatClient] = []
        for entity in entities:
            client = self._create_enemy_decision_client(entity)
            if client is not None:
                chat_clients.append(client)

        if not chat_clients:
            logger.warning("EnemyPlayDecisionSystem: 没有可推理的敌人实体，跳过")
            return

        # 并行 LLM 推理
        await ChatClient.batch_chat(clients=chat_clients)

        # 解析并替换 PlayCardsAction
        for client in chat_clients:
            found_entity = self._game.get_entity_by_name(client.name)
            if found_entity is None:
                logger.error(f"EnemyPlayDecisionSystem: 无法找到实体 {client.name}")
                continue
            self._process_enemy_decision(found_entity, client)

    ####################################################################################################################################
    def _create_enemy_decision_client(self, entity: Entity) -> ChatClient | None:
        """为单个敌人实体创建出牌决策的 ChatClient。

        Args:
            entity: 敌人实体

        Returns:
            ChatClient，若缺少必要组件则返回 None
        """
        hand_comp = entity.get(HandComponent)
        if hand_comp is None or len(hand_comp.cards) == 0:
            logger.error(
                f"EnemyPlayDecisionSystem: 敌人 {entity.name} 没有手牌，无法决策"
            )
            return None

        stats_comp = entity.get(CharacterStatsComponent)
        if stats_comp is None:
            logger.error(
                f"EnemyPlayDecisionSystem: 敌人 {entity.name} 缺少 CharacterStatsComponent"
            )
            return None

        # 获取场上存活的远征队成员名称（对手，不传入血量）
        alive_actors = self._game.get_alive_actors_in_stage(entity)
        opponent_names: List[str] = [
            actor.name for actor in alive_actors if actor.has(ExpeditionMemberComponent)
        ]

        # 获取本回合行动序列信息
        latest_round = self._game.current_dungeon.latest_round
        action_order: List[str] = latest_round.action_order if latest_round else []
        completed_actors: List[str] = (
            latest_round.completed_actors if latest_round else []
        )

        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        prompt = _generate_enemy_decision_prompt(
            enemy_name=entity.name,
            enemy_stats=stats_comp,
            hand_cards=hand_comp.cards,
            opponent_names=opponent_names,
            action_order=action_order,
            completed_actors=completed_actors,
            current_round_number=current_round_number,
        )

        return ChatClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )

    ####################################################################################################################################
    def _process_enemy_decision(self, entity: Entity, client: ChatClient) -> None:
        """解析 LLM 决策响应，替换敌人的 PlayCardsAction。

        Args:
            entity: 敌人实体
            client: 包含 LLM 响应的 ChatClient
        """
        try:
            decision = EnemyDecisionResponse.model_validate_json(
                extract_json_from_code_block(client.response_content)
            )

            hand_comp = entity.get(HandComponent)
            assert hand_comp is not None

            selected_card = next(
                (c for c in hand_comp.cards if c.name == decision.card_name),
                None,
            )
            if selected_card is None:
                logger.error(
                    f"EnemyPlayDecisionSystem: [{entity.name}] LLM 返回的卡牌名 '{decision.card_name}' "
                    f"不在手牌中：{[c.name for c in hand_comp.cards]}，保留空卡"
                )
                return

            # 过滤掉不存在的目标名（防止 ArbitrationActionSystem 出现 warning）
            alive_actors = self._game.get_alive_actors_in_stage(entity)
            alive_names = {a.name for a in alive_actors}
            valid_targets = [t for t in decision.targets if t in alive_names]
            if len(valid_targets) != len(decision.targets):
                logger.warning(
                    f"EnemyPlayDecisionSystem: [{entity.name}] 过滤无效目标 "
                    f"{set(decision.targets) - alive_names}"
                )

            # 写对话历史
            current_round_number = len(self._game.current_dungeon.current_rounds or [])
            self._game.add_human_message(
                entity=entity,
                message_content=client.prompt,
                draw_cards_round_number=current_round_number,
            )
            self._game.add_ai_message(entity, client.response_ai_messages)

            # 替换 PlayCardsAction，填入真实卡牌和目标
            entity.replace(PlayCardsAction, entity.name, selected_card, valid_targets)
            logger.debug(
                f"EnemyPlayDecisionSystem: [{entity.name}] 决策出牌 '{selected_card.name}'，目标：{valid_targets}"
            )

        except Exception as e:
            logger.error(f"{client.response_content}")
            logger.error(
                f"EnemyPlayDecisionSystem: [{entity.name}] 解析 LLM 响应失败，保留空卡。Exception: {e}"
            )

    ####################################################################################################################################
