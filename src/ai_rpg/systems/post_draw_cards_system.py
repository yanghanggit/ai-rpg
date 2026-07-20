"""
DRAW 阶段后置处理系统模块：对存在 DRAW 阶段状态效果的实体，并发调用 LLM 对已抽得手牌进行改动。
当前实现为按状态效果调整已有卡牌的数值，未来可扩展为插入/删除手牌，统称为 DRAW 阶段的通用后置处理。
"""

from typing import Final, List, final, override, Dict
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import (
    compute_character_stats,
    get_status_effects_by_phase,
)
from ..models import (
    ActorComponent,
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
)
from ..utils import extract_json_from_code_block


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
    cost: int = 1
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
        f"| {i + 1} | {c.name} | {c.description} | {c.cost} | {c.damage_dealt} | {c.energy_delta} | {c.hit_count} | {c.target_type.value} |"
        for i, c in enumerate(drawn_cards)
    )

    return f"""# 第 {current_round_number} 回合：根据 DRAW 阶段状态效果调整手牌

## 角色属性

| HP | 攻击 | 防御 | 每回合行动次数 |
|---|---|---|---|
| {actor_stats.hp}/{actor_stats.max_hp} | {actor_stats.attack} | {actor_stats.defense} | {actor_stats.energy} |

## DRAW 阶段状态效果

{effects_lines}

## 当前手牌

| # | name | description | cost | damage_dealt | energy_delta | hit_count | target_type |
|---|---|---|---|---|---|---|---|
{cards_rows}

## 任务

根据以上 DRAW 阶段状态效果，调整每张手牌的数值，使其体现状态效果的影响（如某状态效果使本回合手牌费用增加，可调整 `cost`）。

**可修改字段**：`description`、`affixes`、`modifiers`、`playable`、`exhaust`、`cost`、`damage_dealt`、`energy_delta`、`hit_count`、`target_type`

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
      "cost": 1,
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
class PostDrawCardsSystem(ReactiveProcessor):
    """
    DRAW 阶段的通用后置处理钩子：响应 DrawCardsAction，对存在 DRAW 阶段状态效果的实体
    并发调用 LLM 按效果内容改动已抽得手牌（当前实现为数值调整，未来可扩展为插入/删除卡牌）。
    """

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(DrawCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(DrawCardsAction)
            and entity.has(HandComponent)
            and entity.has(ActorComponent)
            and entity.has(CharacterStatsComponent)
            and not entity.has(DeathComponent)
        )

    ######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_combat_room.combat.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，PostDrawCardsSystem 不执行")
            return

        current_rounds = self._game.current_combat_room.combat.rounds
        assert (
            current_rounds is not None and len(current_rounds) > 0
        ), "当前回合未创建，检查 CombatRoundTransitionSystem 是否正常执行"

        current_round_number = len(current_rounds)

        # 检查 DRAW 阶段状态效果；有效果时并行 LLM 调整
        entities_with_effects: List[Entity] = [
            entity
            for entity in entities
            if get_status_effects_by_phase(entity, PhaseType.DRAW)
        ]

        if not entities_with_effects:
            # 无 DRAW 效果：原始手牌已由 DrawCardsActionSystem 写入，无需调整
            logger.debug("所有实体无 DRAW 阶段效果，跳过 LLM 调整")
            return

        # 为有 DRAW 效果的实体构建 LLM 调整请求
        chat_clients: List[DeepSeekClient] = []
        for entity in entities_with_effects:

            # 获取角色属性、当前回合数、已抽得手牌和 DRAW 阶段状态效果
            combat_stats = compute_character_stats(entity)
            draw_effects = get_status_effects_by_phase(entity, PhaseType.DRAW)

            # 获取已抽得手牌
            hand = entity.get(HandComponent)
            assert (
                hand is not None
            ), f"[{entity.name}] HandComponent 不存在，无法进行 DRAW 效果调整"

            # 生成 LLM 调整 prompt
            prompt = _generate_adjust_prompt(
                actor_stats=combat_stats,
                current_round_number=current_round_number,
                drawn_cards=hand.cards,
                draw_status_effects=draw_effects,
            )

            # 构建 DeepSeekClient 并加入并行请求列表
            chat_clients.append(
                DeepSeekClient(
                    name=entity.name,
                    prompt=prompt,
                    context=self._game.get_agent_context(entity).context,
                )
            )

        # 并行发送所有 LLM 请求，等待所有实体的 DRAW 阶段调整完成
        await DeepSeekClient.batch_chat(clients=chat_clients)

        # 解析调整结果并写入 HandComponent（未被调整的实体已持有 DrawCardsActionSystem 写入的原始手牌）
        for entity in entities_with_effects:
            chat_client = next(c for c in chat_clients if c.name == entity.name)
            hand = entity.get(HandComponent)
            assert (
                hand is not None
            ), f"[{entity.name}] HandComponent 不存在，无法进行 DRAW 效果调整"

            # 解析 LLM 调整响应并写入 HandComponent，解析失败时保留原始手牌
            self._process_adjust_response(
                chat_client=chat_client,
                original_cards=hand.cards,
                current_round_number=current_round_number,
            )

    #######################################################################################################################################
    def _process_adjust_response(
        self,
        chat_client: DeepSeekClient,
        original_cards: List[Card],
        current_round_number: int,
    ) -> None:
        """解析 LLM 调整响应并写入 HandComponent。解析失败时保留原始（未调整）手牌。"""

        # 根据 chat_client 的名字获取对应的实体对象，确保后续操作有正确的实体上下文
        entity = self._game.get_entity_by_name(chat_client.name)
        assert entity is not None, f"无法找到角色实体: {chat_client.name}"

        # 检查 LLM 是否返回了有效的 AI 消息，若无则回退使用原始抽取手牌
        if chat_client.response_ai_message is None:
            logger.error(f"[{entity.name}] LLM 返回空响应，DRAW 效果调整回退为原始手牌")
            return

        # 尝试解析 LLM 返回的 JSON 内容，构建 DrawAdjustResponse 对象
        try:
            response = DrawAdjustResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )
        except Exception as e:
            logger.error(
                f"PostDrawCardsSystem 调整失败: {e}\n{chat_client.response_content}"
            )
            return

        valid_target_types = {e.value for e in TargetType}
        adjusted_cards: List[Card] = []
        for i, entry in enumerate(response.cards):

            # 验证 target_type 字段值是否合法，非法则跳过该卡并发出警告
            if i >= len(original_cards):
                break

            # 如果 target_type 无效，则保留原始牌的 target_type
            if entry.target_type not in valid_target_types:
                logger.warning(
                    f"[{entity.name}] 调整后卡牌「{entry.name}」target_type 无效 {entry.target_type!r}，保留原值"
                )
                entry.target_type = original_cards[i].target_type.value

            # 构建调整后的 Card 对象，保留原始牌的 uuid 和 source，确保跨系统身份一致
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
                    cost=entry.cost,
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

        # 将本轮的 prompt 和 AI 回复写入 agent 上下文，保持对话连续性
        self._game.add_human_message(
            entity=entity,
            human_message=HumanMessage(
                content=chat_client.prompt,
                draw_cards_round_number=current_round_number,
            ),
        )
        self._game.add_ai_message(
            entity,
            chat_client.response_ai_message.model_copy(
                update={"draw_cards_round_number": current_round_number}
            ),
        )

        # 将调整后的手牌写入实体的 HandComponent，确保后续系统使用的是最新的手牌
        entity.replace(HandComponent, entity.name, adjusted_cards)
        logger.debug(
            f"[{entity.name}] DRAW 效果调整后手牌 {len(adjusted_cards)} 张：{[c.name for c in adjusted_cards]}"
        )

    #######################################################################################################################################
