"""
牌库生成系统模块
"""

import random
from enum import IntEnum, unique
from typing import Dict, Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    DeckComponent,
    DrawPileComponent,
    DeathComponent,
    GenerateDeckAction,
    CharacterStats,
    CharacterStatsComponent,
    KeywordComponent,
    Card,
    TargetType,
)
from ..utils import extract_json_from_code_block


###############################################################################################################################################
@final
@unique
class DiceValue(IntEnum):
    """骰值范围常量（0-100 均匀随机整数）"""

    MIN = 0
    MAX = 100


#######################################################################################################################################
@final
class DeckCardEntry(BaseModel):
    """单张卡牌条目（用于 DeckGenerateResponse 解析）"""

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
class DeckGenerateResponse(BaseModel):
    """LLM 一次生成 num_cards 张牌库卡牌的响应模型"""

    cards: List[DeckCardEntry]


#######################################################################################################################################
def _sample_keywords(keywords: List[str], k: int) -> List[str]:
    """从关键词池中采样 k 个关键词，优先不重复，池不足时降级为有放回采样。"""
    if not keywords:
        return []
    if len(keywords) >= k:
        return random.sample(keywords, k=k)
    return random.choices(keywords, k=k)


#######################################################################################################################################
def _build_design_principle_prompt(
    num_cards: int,
    keywords: List[str],
    dice_rolls: List[int] = [],
) -> str:
    """生成关键词约束段落。无关键词时输出差异化指引；有骰值时附加于各卡约束行末。"""
    if not keywords:
        return (
            f"关键词约束：无（{num_cards}张卡牌应有差异化，如高伤低防/高防低伤/均衡型）"
        )
    use_dice = len(dice_rolls) == len(keywords)
    header = (
        "关键词约束（按顺序对应；骰值仅在约束中明确说明用法时生效，否则忽略）："
        if use_dice
        else "关键词约束（按顺序对应）："
    )
    lines = "\n".join(
        f"  - 卡牌{i + 1}：{keywords[i]}"
        + (f"（骰值：{dice_rolls[i]}）" if use_dice else "")
        for i in range(len(keywords))
    )
    return f"{header}\n{lines}"


#######################################################################################################################################
def _generate_deck_prompt(
    actor_stats: CharacterStats,
    num_cards: int,
    keywords: List[str] = [],
    dice_rolls: List[int] = [],
) -> str:
    """生成战斗开始牌库生成 prompt（含字段说明与 JSON 示例）。"""

    design_principle = _build_design_principle_prompt(num_cards, keywords, dice_rolls)

    return f"""\
# 战斗开始：生成 {num_cards} 张初始牌库卡牌

## 角色属性

| HP | 攻击 | 防御 |
|---|---|---|
| {actor_stats.hp}/{actor_stats.max_hp} | {actor_stats.attack} | {actor_stats.defense} |

## 设计约束

{design_principle}

## 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| name | str | 富有想象力，体现行动意图 |
| description | str | 战斗行为的艺术性叙述（1句，第三人称），描述动作风格与角色气质；不含数值，不转述已由其他字段表达的机械效果，不出现"我"等第一人称指代 |
| affixes | list[str] | 延迟词缀，格式 `[名称]:触发倾向`；仅描述数值字段未涵盖的额外持续效果；无则 [] |
| modifiers | list[str] | 即时修正词缀，格式 `[名称]:即时修正`；仅描述数值字段未涵盖的即时修正；无则 [] |
| playable | bool | 是否可出牌；默认 true |
| exhaust | bool | 出牌后是否永久消耗；默认 false |
| damage_dealt | int | 单次伤害值（参考攻击力合理推算） |
| energy_delta | int | 改变目标行动次数（正值增加，负值剥夺）；默认 0 |
| hit_count | int | 攻击次数；默认 1，多段可设 2~4 |
| target_type | str | enemy_single / enemy_all / enemy_random_multi / ally_single / ally_all / self_only |

## 约束

- `description` 禁止提及任何场景地物（如断柱、沙地）、地名或即时情境细节，禁止含数字
- `affixes`/`modifiers` 禁止重述数值字段已确定性表达的效果：`energy_delta ≠ 0` 时不得描述行动次数变化；不得重复量化 `damage_dealt`/`hit_count` 已决定的伤害量级
- `cards` 数组长度必须恰好为 {num_cards}
- 只输出 JSON，不附加任何说明文字

```json
{{
  "cards": [
    {{
      "name": "...",
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
```"""


#######################################################################################################################################
def _generate_compressed_deck_prompt(
    actor_stats: CharacterStats,
    num_cards: int,
    keywords: List[str] = [],
    dice_rolls: List[int] = [],
) -> str:
    """生成牌库生成 prompt 的压缩版（写入对话历史，减少 token 消耗）。"""
    design_principle = _build_design_principle_prompt(num_cards, keywords, dice_rolls)
    return f"""\
# 战斗牌库生成（{num_cards} 张）

HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense}

{design_principle}"""


#######################################################################################################################################
@final
class DeckGenerationSystem(ReactiveProcessor):
    """
    响应 GenerateDeckAction，为每个触发角色并行调用 LLM 生成初始牌库卡牌，
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(GenerateDeckAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GenerateDeckAction)
            and entity.has(ActorComponent)
            and entity.has(DeckComponent)
            and entity.has(DrawPileComponent)
            and entity.has(CharacterStatsComponent)
            and entity.has(KeywordComponent)
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        logger.debug(f"DeckGenerationSystem: 为 {len(entities)} 个角色生成初始牌库")

        # 构建并行 LLM 请求
        chat_clients: List[DeepSeekClient] = []
        num_cards_map: Dict[str, int] = {}  # entity.name -> num_cards
        for entity in entities:

            # 从 GenerateDeckAction 读取本角色的卡牌数
            generate_deck_action = entity.get(GenerateDeckAction)
            assert generate_deck_action is not None
            num_cards = generate_deck_action.num_cards
            num_cards_map[entity.name] = num_cards

            # 获取角色关键词
            combat_stats = self._game.compute_character_stats(entity)

            keyword_comp = entity.get(KeywordComponent)
            # keywords = keyword_comp.keywords if keyword_comp is not None else []
            sampled_keywords = _sample_keywords(keyword_comp.keywords, k=num_cards)

            dice_rolls = [
                random.randint(DiceValue.MIN, DiceValue.MAX) for _ in range(num_cards)
            ]
            logger.debug(
                f"[{entity.name}] 关键词: {[k[:20] for k in sampled_keywords]}  骰值: {dice_rolls}"
            )

            prompt = _generate_deck_prompt(
                actor_stats=combat_stats,
                num_cards=num_cards,
                keywords=sampled_keywords,
                dice_rolls=dice_rolls,
            )
            compressed_prompt = _generate_compressed_deck_prompt(
                actor_stats=combat_stats,
                num_cards=num_cards,
                keywords=sampled_keywords,
                dice_rolls=dice_rolls,
            )

            chat_clients.append(
                DeepSeekClient(
                    name=entity.name,
                    prompt=prompt,
                    compressed_prompt=compressed_prompt,
                    context=self._game.get_agent_context(entity).context,
                )
            )

        await DeepSeekClient.batch_chat(clients=chat_clients)

        # 解析结果，填入 DeckComponent 后洗牌移入 DrawPileComponent
        for chat_client in chat_clients:
            entity1 = self._game.get_entity_by_name(chat_client.name)
            assert (
                entity1 is not None
            ), f"DeckGenerationSystem: 无法找到实体 {chat_client.name} 以处理生成结果"

            self._process_generation_response(
                entity1, chat_client, num_cards_map[chat_client.name]
            )

    #######################################################################################################################################
    def _process_generation_response(
        self,
        entity: Entity,
        chat_client: DeepSeekClient,
        num_cards: int,
    ) -> None:
        """解析 LLM 响应，将生成卡牌洗牌填入 DrawPileComponent。解析失败时跳过（DrawPile 保持空）。"""

        try:

            # 解析 LLM 响应 JSON
            response = DeckGenerateResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            valid_target_types = {e.value for e in TargetType}
            cards: List[Card] = []
            for entry in response.cards:

                # 验证 target_type 字段值是否合法，非法则跳过该卡并发出警告
                if entry.target_type not in valid_target_types:
                    warn_msg = (
                        f"[系统警告] 你刚才生成的牌库卡牌「{entry.name}」的 target_type 字段值为"
                        f"「{entry.target_type}」，不属于有效值（{sorted(valid_target_types)}），"
                        f"该卡已被系统废弃。"
                    )
                    logger.warning(
                        f"[{entity.name}] 牌库卡牌「{entry.name}」target_type 无效，已废弃：{entry.target_type!r}"
                    )
                    self._game.add_human_message(
                        entity=entity, message_content=warn_msg
                    )
                    continue

                cards.append(
                    Card(
                        name=entry.name,
                        description=entry.description,
                        affixes=entry.affixes,
                        modifiers=entry.modifiers,
                        playable=entry.playable,
                        exhaust=entry.exhaust,
                        damage_dealt=entry.damage_dealt,
                        energy_delta=entry.energy_delta,
                        hit_count=entry.hit_count,
                        target_type=TargetType(entry.target_type),
                        source=entity.name,
                    )
                )

            if len(cards) != num_cards:
                logger.warning(
                    f"[{entity.name}] 牌库生成卡牌数量（{len(cards)}）与预期（{num_cards}）不符"
                )

            # 累积到原始牌库：本次新生成的牌追加到 DeckComponent
            deck_comp = entity.get(DeckComponent)
            assert deck_comp is not None, f"{entity.name} 缺少 DeckComponent"
            deck_comp.cards.extend(cards)

            # 洗牌后将本次新牌副本追加到 DrawPile（只操作本批次 cards，不受历史牌影响）
            random.shuffle(cards)
            draw_pile = entity.get(DrawPileComponent)
            assert draw_pile is not None, f"{entity.name} 缺少 DrawPileComponent"
            draw_pile.cards.extend([c.model_copy() for c in cards])

            # 将本轮任务提示词与 LLM 回复写入 agent 对话历史
            self._game.add_human_message(
                entity=entity,
                message_content=chat_client.compressed_prompt,
                deck_generation_full_prompt=chat_client.prompt,
            )
            assert chat_client.response_ai_message is not None
            self._game.add_ai_message(
                entity=entity, ai_message=chat_client.response_ai_message
            )

            logger.debug(
                f"[{entity.name}] 牌库生成完成：本次 {len(cards)} 张副本已洗牌填入 DrawPile"
                f"，DeckComponent 共 {len(deck_comp.cards)} 张原始牌（含本次）"
                f"：{[c.name for c in cards]}"
            )

        except Exception as e:
            logger.error(
                f"DeckGenerationSystem 解析失败 [{entity.name}]: {e}\n{chat_client.response_content}"
            )
            # 解析失败：DrawPile 保持空，DrawCardsActionSystem 回合首次抽牌时会插入兜底牌
