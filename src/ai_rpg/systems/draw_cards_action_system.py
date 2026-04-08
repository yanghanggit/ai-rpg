"""
卡牌抽取系统模块

该模块实现了战斗回合中的卡牌生成机制，通过 LLM 一次性为每个角色生成多张行动卡牌。

核心特性：
- 批量多卡生成：每个 DrawCardsAction 触发一次 LLM 请求，生成 num_cards 张风格各异的卡牌
- LLM 驱动：通过语言模型生成富有创意且符合角色属性的卡牌名称、行动描述和攻防数值
- 批量推理：所有角色的 LLM 请求并行发出（ChatClient.batch_chat），结果逐一解析写入 HandComponent

主要组件：
- DrawCardsActionSystem: 核心系统类，协调整个卡牌生成流程
- _generate_draw3_prompt: 生成"一次抽 num_cards 张卡"的 LLM 提示词
- CardEntry / Draw3CardsResponse: LLM 响应的 Pydantic 解析模型
"""

from typing import Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    DrawCardsAction,
    HandComponent,
    Card,
    CardTargetType,
    DeathComponent,
    CharacterStats,
    CharacterStatsComponent,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class CardEntry(BaseModel):
    """单张卡牌条目（用于 DrawCardsResponse 解析）"""

    name: str
    action: str
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
) -> str:
    """生成"一次生成 num_cards 张 Card2"的提示词。

    Args:
        actor_stats: 角色当前属性（hp/max_hp/attack/defense）
        current_round_number: 当前回合数
        num_cards: 要求生成的卡牌数量

    Returns:
        格式化的完整提示词
    """
    actor_stats_prompt = f"HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense}"
    cards_example = "\n    ".join(
        f'{{"name": "卡牌名{i + 1}", "action": "第一人称行动描述", "damage_dealt": 0, "block_gain": 0, "hit_count": 1, "target_type": "enemy_single"}}'
        for i in range(num_cards)
    )

    return f"""# 指令！第 {current_round_number} 回合：生成{num_cards}张战斗卡牌(JSON)

根据角色当前状态，发挥创意生成{num_cards}张风格各异的战斗卡牌。每张卡牌代表一种可执行的战斗选择。

## 输入

**属性**: {actor_stats_prompt}

## 格式要求

**命名**: 富有想象力的卡牌名称，体现行动意图

**字段说明**:
- **action** - 第一人称行动描述（1-2句，生动具体）
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

    负责在战斗回合中为每个参战角色批量生成行动卡牌（Hand）。

    工作流程：
    1. 接收 DrawCardsAction 触发（每个存活角色各一个）
    2. 清除各实体旧有的 HandComponent
    3. 为每个角色调用 _create_draw_chat_client，向 LLM 请求生成 num_cards 张差异化卡牌：
       - 传入角色当前 CombatStatsComponent 属性（HP/攻击/防御）
    4. 所有请求并行执行（ChatClient.batch_chat）
    5. 逐一调用 _process_draw_response 解析 LLM 响应，写入 HandComponent
    """

    def __init__(self, game: TCGGame, num_cards: int) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
        self._num_cards: Final[int] = num_cards  # 每次抽取的卡牌数量

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
            # if entity.has(HandComponent):
            #     logger.debug(
            #         f"实体 {entity.name} 已有 HandComponent，可能是上回合遗留，先行移除"
            #     )
            #     entity.remove(HandComponent)

        # 为每个 entity 创建 draw3 聊天客户端
        chat_clients: List[ChatClient] = []
        for entity in entities:
            chat_client = self._create_draw_chat_client(
                entity=entity, num_cards=self._num_cards
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
                found_entity, chat_client, num_cards=self._num_cards
            )

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

        prompt = _generate_draw_prompt(
            actor_stats=combat_stats_comp.stats,
            current_round_number=current_round_number,
            num_cards=num_cards,
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
    ) -> None:
        """解析 LLM 返回的卡牌，写入 HandComponent。

        Args:
            entity: 目标角色实体
            chat_client: 包含 LLM 响应的聊天客户端
            num_cards: 预期的卡牌数量
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
                        action=entry.action,
                        damage_dealt=entry.damage_dealt,
                        block_gain=entry.block_gain,
                        hit_count=entry.hit_count,
                        target_type=CardTargetType(entry.target_type),
                    )
                )

            if len(cards) != num_cards:
                logger.warning(
                    f"[{entity.name}] 过滤后卡牌数量（{len(cards)}）与预期（{num_cards}）不符，"
                    "可能有部分卡牌因无效 target_type 被废弃"
                )

            entity.replace(HandComponent, entity.name, cards, current_round_number)
            logger.debug(
                f"[{entity.name}] 生成 {len(cards)} 张 Card2：{[c.name for c in cards]}"
            )

        except Exception as e:
            logger.error(f"{chat_client.response_content}")
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
