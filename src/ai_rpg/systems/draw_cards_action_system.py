"""
卡牌抽取系统模块

该模块实现了战斗回合中的卡牌生成机制，结合历史牌组复用与 LLM 实时生成，为每个角色填充手牌。

核心特性：
- 历史牌优先：优先从 DeckComponent 取最多 max_num_cards - 1 张历史牌（FIFO 消耗语义）
- 保证新鲜度：无论 Deck 是否充裕，每回合至少 1 张由 LLM 实时生成
- 批量推理：所有角色的 LLM 请求并行发出（ChatClient.batch_chat），结果逐一解析写入 HandComponent
- 合并写入：Deck 历史牌（前）+ LLM 新生成牌（后）合并为最终手牌

主要组件：
- DrawCardsActionSystem: 核心系统类，协调 Deck 消耗与 LLM 生成流程
- _generate_draw_prompt: 生成"一次生成 num_cards 张卡"的 LLM 提示词
- CardEntry / DrawCardsResponse: LLM 响应的 Pydantic 解析模型
"""

from typing import Dict, Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    DeckComponent,
    DrawCardsAction,
    HandComponent,
    Card,
    CardTargetType,
    DeathComponent,
    CharacterStats,
    CharacterStatsComponent,
    StatusEffectsComponent,
    StatusEffect,
    StatusEffectPhase,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class CardEntry(BaseModel):
    """单张卡牌条目（用于 DrawCardsResponse 解析）"""

    name: str
    description: str
    status_effect_hint: str = (
        ""  # 可能触发的持续性状态效果暗示；为空时仲裁后不触发 AddStatusEffectsAction LLM 推理
    )
    damage_dealt: int
    block_gain: int
    hit_count: int = 1
    target_type: str = CardTargetType.ENEMY_SINGLE  # 接受原始字符串，由系统逐卡校验


#######################################################################################################################################
@final
class DrawCardsResponse(BaseModel):
    """LLM 一次抽取 num_cards 张卡牌的响应模型"""

    cards: List[CardEntry]


#######################################################################################################################################
def _generate_draw_prompt(
    actor_stats: CharacterStats,
    current_round_number: int,
    num_cards: int,
    draw_status_effects: List[StatusEffect],
) -> str:
    """生成"一次生成 num_cards 张 Card2"的提示词。

    Args:
        actor_stats: 角色当前属性（hp/max_hp/attack/defense）
        current_round_number: 当前回合数
        num_cards: 要求生成的卡牌数量
        draw_status_effects: 当前 draw 阶段的状态效果列表，影响卡牌数值生成

    Returns:
        格式化的完整提示词
    """
    actor_stats_prompt = f"HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense}"

    def _fmt_duration(d: int) -> str:
        return "永久" if d == -1 else f"剩余{d}回合"

    if draw_status_effects:
        effects_lines = "\n".join(
            f"- {e.name}（{_fmt_duration(e.duration)}）: {e.description}"
            for e in draw_status_effects
        )
        draw_effects_prompt = f"**抽牌状态效果**（请据此调整卡牌数值，attack 影响 damage_dealt，defense 影响 block_gain）:\n{effects_lines}"
    else:
        draw_effects_prompt = "**抽牌状态效果**: 无"

    cards_example = "\n    ".join(
        f'{{"name": "卡牌名{i + 1}", "description": "第三人称通用描述", "status_effect_hint": "", "damage_dealt": 0, "block_gain": 0, "hit_count": 1, "target_type": "enemy_single"}}'
        for i in range(num_cards)
    )

    return f"""# 第 {current_round_number} 回合：生成{num_cards}张战斗卡牌(JSON)

根据角色当前状态，发挥创意生成{num_cards}张风格各异的战斗卡牌。每张卡牌代表一种可执行的战斗选择。

## 输入

**属性**: {actor_stats_prompt}

{draw_effects_prompt}

## 格式要求

**命名**: 富有想象力的卡牌名称，体现行动意图

**字段说明**:
- **description** - 第三人称通用描述（1句，客观说明这张牌的即时战斗行为，不绑定具体场景，如"投掷附近碎石对单一目标造成中等伤害"）
- **status_effect_hint** - 可能触发的持续性状态效果暗示（1句，如"可能引发燃烧、中毒、虚弱等持续加深效果"）；若该卡仅为即时伤害/格挡无副作用，则留空字符串""（为空时系统不触发后续 LLM 推理，节省开销）
- **damage_dealt** - 单次攻击造成的伤害值（基于攻击力合理推算，整数）
- **block_gain** - 本张卡牌提供的格挡增量（基于防御力合理推算，整数）
- **hit_count** - 攻击次数（默认 1；多段攻击如回旋镖可设为 2~4，每段独立抵挡目标格挡）
- **target_type** - 出牌目标类型：攻击/伤害类卡牌通常选 `enemy_single` 或 `enemy_all`；治疗/强化友方类卡牌通常选 `ally_single` 或 `ally_all`；纯粹的自我防御、呼吸调息等仅作用于自身的卡牌选 `self_only`

**设计原则**: {num_cards}张卡牌应有差异化——可以是高伤低防、高防低伤、均衡型等不同侧重

## 输出JSON

```json
{{
  "cards": [
    {cards_example}
  ]
}}
```"""


#######################################################################################################################################
@final
class DrawCardsActionSystem(ReactiveProcessor):
    """
    卡牌抽取系统

    负责在战斗回合中为每个参战角色填充手牌（Hand）。

    工作流程：
    1. 接收 DrawCardsAction 触发（每个存活角色各一个）
    2. 预处理：从每个实体的 DeckComponent FIFO 消耗最多 max_num_cards - 1 张历史牌
    3. 为每个角色调用 _create_draw_chat_client，向 LLM 请求生成剩余张数（≥1）的新卡牌
    4. 所有请求并行执行（ChatClient.batch_chat）
    5. 逐一调用 _process_draw_response，合并 Deck 历史牌 + LLM 新牌，写入 HandComponent
    """

    def __init__(self, game: TCGGame, max_num_cards: int) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
        assert (
            max_num_cards >= 1
        ), "max_num_cards 必须至少为 1，保证每回合至少生成 1 张新牌"
        self._max_num_cards: Final[int] = max_num_cards  # 每次抽取的卡牌数量

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(DrawCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(DrawCardsAction)
            and entity.has(ActorComponent)
            and not entity.has(DeathComponent)
            and not entity.has(HandComponent)  # 确保没有旧的 HandComponent
        )

    ######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

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
        logger.debug(f"当前回合数: {len(current_rounds)}")

        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None, "无法获取当前回合信息！"

        # 清除手牌（如果有）以避免旧数据干扰
        for entity in entities:
            assert not entity.has(
                HandComponent
            ), f"实体 {entity.name} 已有 HandComponent，可能是上回合遗留，先行移除"

        # 预处理：从每个实体的 DeckComponent FIFO 消耗历史牌
        entity_deck_cards, entity_generate_counts = self._consume_deck_cards(entities)

        # 为每个 entity 创建 draw 聊天客户端
        chat_clients: List[ChatClient] = []
        for entity in entities:
            chat_client = self._create_draw_chat_client(
                entity=entity, num_cards=entity_generate_counts[entity.name]
            )
            chat_clients.append(chat_client)

        # 批量 LLM 推理
        await ChatClient.batch_chat(clients=chat_clients)

        # 处理响应，写入 HandComponent
        for chat_client in chat_clients:
            found_entity = self._game.get_entity_by_name(chat_client.name)
            assert (
                found_entity is not None
            ), f"Entity {chat_client.name} not found in game."
            self._process_draw_response(
                found_entity,
                chat_client,
                num_cards=entity_generate_counts[found_entity.name],
                deck_cards=entity_deck_cards[found_entity.name],
            )

    #######################################################################################################################################
    def _consume_deck_cards(
        self, entities: list[Entity]
    ) -> tuple[Dict[str, List[Card]], Dict[str, int]]:
        """从每个实体的 DeckComponent FIFO 消耗历史牌，计算本回合各实体需 LLM 生成的张数。

        最多消耗 max_num_cards - 1 张，保证至少 1 张由 LLM 新生成。

        Args:
            entities: 本回合需要抽牌的实体列表

        Returns:
            entity_deck_cards: entity.name -> 已消耗的历史牌列表
            entity_generate_counts: entity.name -> 本回合需 LLM 生成的张数
        """
        entity_deck_cards: Dict[str, List[Card]] = {}
        entity_generate_counts: Dict[str, int] = {}
        for entity in entities:
            deck_comp = entity.get(DeckComponent)
            assert deck_comp is not None, f"实体 {entity.name} 缺少 DeckComponent"
            n_from_deck = min(len(deck_comp.cards), self._max_num_cards - 1)
            deck_cards = list(deck_comp.cards[:n_from_deck])
            del deck_comp.cards[:n_from_deck]
            entity_deck_cards[entity.name] = deck_cards
            entity_generate_counts[entity.name] = self._max_num_cards - n_from_deck
            logger.debug(
                f"[{entity.name}] 从 Deck 取 {n_from_deck} 张历史牌，"
                f"需 LLM 生成 {entity_generate_counts[entity.name]} 张"
            )
        return entity_deck_cards, entity_generate_counts

    #######################################################################################################################################
    def _create_draw_chat_client(
        self,
        entity: Entity,
        num_cards: int,
    ) -> ChatClient:
        """为单个角色创建"生成 num_cards 张 Card2"的聊天客户端。

        Args:
            entity: 角色实体
            num_cards: 要求生成的卡牌数量

        Returns:
            ChatClient: 已填充提示词的聊天客户端
        """
        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None
        assert (
            not last_round.is_round_completed
        ), "当前没有进行中的战斗回合，不能生成卡牌。"

        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        combat_stats_comp = entity.get(CharacterStatsComponent)
        assert (
            combat_stats_comp is not None
        ), f"Entity {entity.name} must have CombatStatsComponent"

        status_effects_comp = entity.get(StatusEffectsComponent)
        draw_effects = [
            e
            for e in (
                status_effects_comp.status_effects
                if status_effects_comp is not None
                else []
            )
            if e.phase == StatusEffectPhase.DRAW
        ]

        prompt = _generate_draw_prompt(
            actor_stats=combat_stats_comp.stats,
            current_round_number=current_round_number,
            num_cards=num_cards,
            draw_status_effects=draw_effects,
        )

        return ChatClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )

    #######################################################################################################################################
    def _process_draw_response(
        self,
        entity: Entity,
        chat_client: ChatClient,
        num_cards: int,
        deck_cards: List[Card],
    ) -> None:
        """解析 LLM 返回的卡牌，与 Deck 历史牌合并后写入 HandComponent。

        Args:
            entity: 目标角色实体
            chat_client: 包含 LLM 响应的聊天客户端
            num_cards: 预期由 LLM 生成的卡牌数量
            deck_cards: 本回合从 DeckComponent 消耗的历史牌（已在 react() 中移除）
        """
        try:
            response = DrawCardsResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            last_round = self._game.current_dungeon.latest_round
            assert last_round is not None
            assert (
                not last_round.is_round_completed
            ), "当前没有进行中的战斗回合，不能写入卡牌。"

            current_round_number = len(self._game.current_dungeon.current_rounds or [])

            # 写入对话历史（原始 prompt + AI 原文）
            self._game.add_human_message(
                entity=entity,
                message_content=chat_client.prompt,
                draw_cards_round_number=current_round_number,
            )
            for ai_message in chat_client.response_ai_messages:
                setattr(ai_message, "draw_cards_round_number", current_round_number)
            self._game.add_ai_message(entity, chat_client.response_ai_messages)

            # 构建 Card 列表：逐卡校验 target_type，非法值废弃并写入 agent 警告
            valid_target_types = {e.value for e in CardTargetType}
            cards: List[Card] = []
            for entry in response.cards:
                if entry.target_type not in valid_target_types:
                    warn_msg = (
                        f"[系统警告] 你刚才生成的卡牌「{entry.name}」的 target_type 字段值为"
                        f"「{entry.target_type}」，不属于有效值（{sorted(valid_target_types)}），"
                        f"该卡已被系统废弃。请在后续生成中确保 target_type 只使用以下值之一：{sorted(valid_target_types)}"
                    )
                    logger.warning(
                        f"[{entity.name}] 卡牌「{entry.name}」target_type 无效，已废弃：{entry.target_type!r}"
                    )
                    self._game.add_human_message(
                        entity=entity, message_content=warn_msg
                    )
                    continue
                cards.append(
                    Card(
                        name=entry.name,
                        description=entry.description,
                        status_effect_hint=entry.status_effect_hint,
                        damage_dealt=entry.damage_dealt,
                        block_gain=entry.block_gain,
                        hit_count=entry.hit_count,
                        target_type=CardTargetType(entry.target_type),
                        source=entity.name,
                    )
                )

            if len(cards) != num_cards:
                logger.warning(
                    f"[{entity.name}] LLM 生成卡牌数量（{len(cards)}）与预期（{num_cards}）不符，"
                    "可能有部分卡牌因无效 target_type 被废弃"
                )

            # 合并：Deck 历史牌（前）+ LLM 新生成牌（后）
            all_cards = deck_cards + cards
            entity.replace(HandComponent, entity.name, all_cards, current_round_number)
            logger.debug(
                f"[{entity.name}] 手牌共 {len(all_cards)} 张 "
                f"= Deck {len(deck_cards)} 张 + 新生成 {len(cards)} 张："
                f"{[c.name for c in all_cards]}"
            )

        except Exception as e:
            logger.error(f"{chat_client.response_content}")
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
