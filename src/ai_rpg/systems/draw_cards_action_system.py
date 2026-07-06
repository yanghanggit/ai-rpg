"""
卡牌抽取系统模块
"""

import random
from typing import Final, List, final, override, Dict
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_entity_ops import compute_character_stats, get_status_effects_by_phase
from ..models import (
    ActorComponent,
    DrawPileComponent,
    DiscardPileComponent,
    DrawCardsAction,
    HandComponent,
    HumanMessage,
    Card,
    TargetType,
    DeathComponent,
    CharacterStats,
    CharacterStatsComponent,
    StatusEffect,
    PhaseType,
    PartyMemberComponent,
    MonsterComponent,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
# 兜底牌常量
_FALLBACK_CARD_NAME = "等待"
_FALLBACK_CARD_DESCRIPTION = "什么都不做，原地等待。"
_FALLBACK_ADJUST_SYSTEM_MESSAGE = (
    "[系统提示] 本回合手牌调整失败（LLM 响应格式错误），已自动使用原始手牌。"
)


#######################################################################################################################################
@final
class AdjustedCardEntry(BaseModel):
    """调整后的单张卡牌条目（用于 DrawAdjustResponse 解析）"""

    name: str
    description: str
    affixes: List[str] = []
    modifiers: List[str] = []
    playable: bool = True
    exhaust: bool = False
    damage_dealt: int
    energy_delta: int = 0
    hit_count: int = 1
    target_type: str = TargetType.ENEMY_SINGLE


#######################################################################################################################################
@final
class DrawAdjustResponse(BaseModel):
    """LLM 对已抽得手牌进行 DRAW 效果调整的响应模型"""

    cards: List[AdjustedCardEntry]


#######################################################################################################################################
def _generate_adjust_prompt(
    actor_stats: CharacterStats,
    current_round_number: int,
    drawn_cards: List[Card],
    draw_status_effects: List[StatusEffect],
) -> str:
    """生成手牌调整 prompt，要求 LLM 根据 DRAW 阶段状态效果修改已抽得卡牌的数值。"""

    def _fmt_duration(d: int) -> str:
        return "永久" if d == -1 else f"剩余{d}回合"

    effects_lines = "\n".join(
        f"- **{e.name}**（{_fmt_duration(e.duration)}）: {e.description}"
        for e in draw_status_effects
    )

    cards_rows = "\n".join(
        f"| {i + 1} | {c.name} | {c.description} | {c.damage_dealt} | {c.energy_delta} | {c.hit_count} | {c.target_type.value} |"
        for i, c in enumerate(drawn_cards)
    )

    return f"""\
# 第 {current_round_number} 回合：根据状态效果调整手牌

## 角色属性

| HP | 攻击 | 防御 |
|---|---|---|
| {actor_stats.hp}/{actor_stats.max_hp} | {actor_stats.attack} | {actor_stats.defense} |

## DRAW 阶段状态效果

{effects_lines}

## 当前手牌

| # | name | description | damage_dealt | energy_delta | hit_count | target_type |
|---|---|---|---|---|---|---|
{cards_rows}

## 任务

根据以上 DRAW 阶段状态效果，调整每张手牌的数值，使其体现状态效果的影响。

**可修改字段**：`description`、`affixes`、`modifiers`、`playable`、`exhaust`、`damage_dealt`、`energy_delta`、`hit_count`、`target_type`

**不可修改字段**：`name`（用于对位识别，须原样回传）、`uuid`、`source`（系统自动保留，无需输出）

**约束**：`cards` 数组长度必须与输入相同，顺序一一对应。只输出 JSON。

```json
{{
  "cards": [
    {{
      "name": "（原样回传，不得修改）",
      "description": "...",
      "affixes": [],
      "modifiers": [],
      "playable": true,
      "exhaust": false,
      "damage_dealt": 0,
      "energy_delta": 0,
      "hit_count": 1,
      "target_type": "enemy_single"
    }}
  ]
}}
```
"""


#######################################################################################################################################
@final
class DrawCardsActionSystem(ReactiveProcessor):
    """
    响应 DrawCardsAction，为每个存活角色填充 HandComponent。

    从 DrawPileComponent 抽取手牌（FIFO）；DrawPile 耗尽时将 DiscardPile 洗牌整体补入。
    若 DRAW 阶段有状态效果则调用一次 LLM 进行数值调整，否则直接写入 HandComponent。
    """

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    def _get_max_num_cards(self, actor: Entity) -> int:
        """返回角色本回合应持有的手牌上限（PartyMember=3，Monster=1）。"""
        if actor.has(PartyMemberComponent):
            return 3
        if actor.has(MonsterComponent):
            return 1
        return 1

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(DrawCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(DrawCardsAction)
            and entity.has(ActorComponent)
            and entity.has(DrawPileComponent)
            and entity.has(DiscardPileComponent)
            and entity.has(CharacterStatsComponent)
            and not entity.has(DeathComponent)
            and not entity.has(HandComponent)
        )

    ####################################################################################################################################
    def _draw_from_pile(self, entity: Entity, n: int) -> List[Card]:
        """从 DrawPile 抽取 n 张牌（FIFO）。"""
        draw_pile = entity.get(DrawPileComponent)
        discard_pile = entity.get(DiscardPileComponent)
        assert draw_pile is not None and discard_pile is not None

        drawn: List[Card] = []
        while len(drawn) < n:
            if draw_pile.cards:
                drawn.append(draw_pile.cards.pop(0))  # FIFO
            elif discard_pile.cards:
                # DrawPile 耗尽：将 DiscardPile 洗牌补入
                random.shuffle(discard_pile.cards)
                draw_pile.cards.extend(discard_pile.cards)
                discard_pile.cards.clear()
                logger.debug(
                    f"[{entity.name}] DrawPile 耗尽，DiscardPile {len(draw_pile.cards)} 张洗牌补入 DrawPile"
                )
            else:
                # 两堆均空：插入兜底牌
                drawn.append(
                    Card(
                        name=_FALLBACK_CARD_NAME,
                        description=_FALLBACK_CARD_DESCRIPTION,
                        affixes=[],
                        damage_dealt=0,
                        hit_count=1,
                        target_type=TargetType.SELF_ONLY,
                        source=entity.name,
                    )
                )
                logger.warning(
                    f"[{entity.name}] DrawPile 与 DiscardPile 均空，插入兜底牌「{_FALLBACK_CARD_NAME}」"
                )
                break

        return drawn

    ######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，DrawCardsActionSystem 不执行")
            return

        logger.debug(
            f"DrawCardsActionSystem: 处理 {len(entities)} 个实体的 DrawCardsAction"
        )

        current_rounds = self._game.current_dungeon.current_rounds
        assert (
            current_rounds is not None and len(current_rounds) > 0
        ), "当前回合未创建，检查 CombatRoundTransitionSystem 是否正常执行"

        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None, "无法获取当前回合信息！"
        current_round_number = len(current_rounds)

        # 第一步：从 DrawPile 抽牌（含 DiscardPile reshuffle 逻辑）
        entity_drawn_cards: Dict[str, List[Card]] = {}
        for entity in entities:
            n = self._get_max_num_cards(entity)
            drawn = self._draw_from_pile(entity, n)
            entity_drawn_cards[entity.name] = drawn
            logger.debug(
                f"[{entity.name}] 抽取 {len(drawn)} 张：{[c.name for c in drawn]}"
            )

        # 第二步：检查 DRAW 阶段状态效果；有效果时并行 LLM 调整
        entities_with_effects: List[Entity] = [
            entity
            for entity in entities
            if get_status_effects_by_phase(entity, PhaseType.DRAW)
        ]

        if not entities_with_effects:
            # 无 DRAW 效果：直接写入 HandComponent
            for entity in entities:
                entity.replace(
                    HandComponent,
                    entity.name,
                    entity_drawn_cards[entity.name],
                    # current_round_number,
                )
            logger.debug("所有实体无 DRAW 阶段效果，跳过 LLM 直接写入手牌")
            last_round.draw_completed = True
            return

        # 为有 DRAW 效果的实体构建 LLM 调整请求
        chat_clients: List[DeepSeekClient] = []
        for entity in entities_with_effects:
            combat_stats = compute_character_stats(entity)
            draw_effects = get_status_effects_by_phase(entity, PhaseType.DRAW)
            prompt = _generate_adjust_prompt(
                actor_stats=combat_stats,
                current_round_number=current_round_number,
                drawn_cards=entity_drawn_cards[entity.name],
                draw_status_effects=draw_effects,
            )
            chat_clients.append(
                DeepSeekClient(
                    name=entity.name,
                    prompt=prompt,
                    context=self._game.get_agent_context(entity).context,
                )
            )

        await DeepSeekClient.batch_chat(clients=chat_clients)

        last_round.draw_completed = True
        # 第三步：解析调整结果并写入 HandComponent
        adjusted_entity_names = {e.name for e in entities_with_effects}
        for entity in entities:
            if entity.name not in adjusted_entity_names:
                entity.replace(
                    HandComponent,
                    entity.name,
                    entity_drawn_cards[entity.name],
                    # current_round_number,
                )
                continue

            chat_client = next(c for c in chat_clients if c.name == entity.name)
            self._process_adjust_response(
                entity=entity,
                chat_client=chat_client,
                original_cards=entity_drawn_cards[entity.name],
                current_round_number=current_round_number,
            )

    #######################################################################################################################################
    def _process_adjust_response(
        self,
        entity: Entity,
        chat_client: DeepSeekClient,
        original_cards: List[Card],
        current_round_number: int,
    ) -> None:
        """解析 LLM 调整响应并写入 HandComponent。解析失败时回退使用原始抽取手牌。"""

        try:
            response = DrawAdjustResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            valid_target_types = {e.value for e in TargetType}
            adjusted_cards: List[Card] = []
            for i, entry in enumerate(response.cards):
                if i >= len(original_cards):
                    break
                if entry.target_type not in valid_target_types:
                    logger.warning(
                        f"[{entity.name}] 调整后卡牌「{entry.name}」target_type 无效 {entry.target_type!r}，保留原值"
                    )
                    entry.target_type = original_cards[i].target_type.value

                orig = original_cards[i]
                adjusted_cards.append(
                    Card(
                        uuid=orig.uuid,  # 保留副本 uuid，确保跨系统身份一致
                        name=orig.name,  # 保持原名
                        description=entry.description,
                        affixes=entry.affixes,
                        modifiers=entry.modifiers,
                        playable=entry.playable,
                        exhaust=entry.exhaust,
                        damage_dealt=entry.damage_dealt,
                        energy_delta=entry.energy_delta,
                        hit_count=entry.hit_count,
                        target_type=TargetType(entry.target_type),
                        source=orig.source,
                        # 首次修改时快照原始牌；若原始牌本身已是副本则保留其快照，确保还原点始终指向最原始版本
                        original_data=(
                            orig if orig.original_data is None else orig.original_data
                        ),
                    )
                )

            # LLM 返回张数不足时用原始牌补足
            if len(adjusted_cards) < len(original_cards):
                adjusted_cards.extend(original_cards[len(adjusted_cards) :])

            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=chat_client.prompt,
                    draw_cards_round_number=current_round_number,
                ),
            )
            assert chat_client.response_ai_message is not None
            self._game.add_ai_message(
                entity,
                chat_client.response_ai_message.model_copy(
                    update={"draw_cards_round_number": current_round_number}
                ),
            )

            entity.replace(HandComponent, entity.name, adjusted_cards)
            logger.debug(
                f"[{entity.name}] DRAW 效果调整后手牌 {len(adjusted_cards)} 张：{[c.name for c in adjusted_cards]}"
            )

        except Exception as e:
            logger.error(
                f"DrawCardsActionSystem 调整失败: {e}\n{chat_client.response_content}"
            )
            # 回退：使用原始抽取手牌，不阻塞回合
            entity.replace(HandComponent, entity.name, original_cards)
            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(content=_FALLBACK_ADJUST_SYSTEM_MESSAGE),
            )
