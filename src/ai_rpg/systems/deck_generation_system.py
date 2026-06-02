"""
牌库生成系统模块

在每场战斗开始时（is_ongoing 且尚无任何回合）为所有存活战斗参与者各生成一批卡牌，
洗牌后填入其 DrawPileComponent，作为本场战斗的初始牌库。

主要组件：
- DeckGenerationSystem: 核心系统类（ExecuteProcessor）
- DeckCardEntry / DeckGenerateResponse: 卡牌生成 LLM 响应的 Pydantic 解析模型
"""

import random
from typing import Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    DeckComponent,
    DrawPileComponent,
    DeathComponent,
    CharacterStats,
    CharacterStatsComponent,
    KeywordComponent,
    Keyword,
    DiceValue,
    Card,
    TargetType,
)
from ..utils import extract_json_from_code_block


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
    hit_count: int = 1
    target_type: str = TargetType.ENEMY_SINGLE


#######################################################################################################################################
@final
class DeckGenerateResponse(BaseModel):
    """LLM 一次生成 num_cards 张牌库卡牌的响应模型"""

    cards: List[DeckCardEntry]


#######################################################################################################################################
def _sample_keywords(keywords: List[Keyword], k: int) -> List[Keyword]:
    """从关键词池中采样 k 个关键词，优先不重复，池不足时降级为有放回采样。"""
    if not keywords:
        return []
    if len(keywords) >= k:
        return random.sample(keywords, k=k)
    return random.choices(keywords, k=k)


#######################################################################################################################################
def _build_design_principle_prompt(
    num_cards: int,
    keywords: List[Keyword],
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
        f"  - 卡牌{i + 1}：{keywords[i].description}"
        + (f"（骰值：{dice_rolls[i]}）" if use_dice else "")
        for i in range(len(keywords))
    )
    return f"{header}\n{lines}"


#######################################################################################################################################
def _generate_deck_prompt(
    actor_stats: CharacterStats,
    num_cards: int,
    keywords: List[Keyword] = [],
    dice_rolls: List[int] = [],
) -> str:
    """生成战斗开始牌库生成 prompt（含字段说明与 JSON 示例）。"""

    design_principle = _build_design_principle_prompt(num_cards, keywords, dice_rolls)

    return f"""# 战斗开始：生成 {num_cards} 张初始牌库卡牌

## 角色属性

HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense}

## 设计约束

{design_principle}

## 字段说明

- name：富有想象力，体现行动意图
- description：第三人称通用描述（1句，客观说明这张牌的即时战斗行为，禁止叙事润色）。
  【重要】禁止提及任何当前场景的地物（如断柱、沙地、余晖、岩板等）、地名或即时情境细节。
  ❌ 错误示例：「借助断柱的支撑旋身，踢击敌人」
  ✓ 正确示例：「旋身借力，以连续踢击攻击单一敌人」
- affixes：延迟词缀列表，格式 `[名称]:触发倾向描述`，出牌后独立推理生成持续状态效果（如 `[燃烧]:可能引发持续扣血`）；无持续效果时输出 []
- modifiers：即时修正词缀列表，格式 `[名称]:即时修正描述`，直接注入本次仲裁计算（如 `[穿甲]:无视目标防御`）；无即时修正时输出 []
- playable：布尔值，是否允许出牌；默认 true
- exhaust：布尔值，出牌后是否永久消耗（归入消耗堆，不进入弃牌循环）；默认 false
- damage_dealt：单次攻击造成的伤害值（基于攻击力合理推算，整数）
- hit_count：攻击次数（默认 1；多段攻击可设为 2~4）
- target_type：目标类型：enemy_single / enemy_all / enemy_random_multi / ally_single / ally_all / self_only

## 输出格式

输出 JSON，cards 数组共 {num_cards} 张：

{{"name":"...","description":"...","affixes":[],"modifiers":[],"playable":true,"exhaust":false,"damage_dealt":0,"hit_count":1,"target_type":"enemy_single"}}"""


#######################################################################################################################################
@final
class DeckGenerationSystem(ExecuteProcessor):
    """
    在每场战斗开始时（is_ongoing 且 current_rounds 为空）为所有存活战斗参与者
    并行调用 LLM 生成初始牌库卡牌，洗牌后填入各角色的 DrawPileComponent。

    触发条件（精确一次）：
        is_ongoing == True  AND  len(current_rounds) == 0
    """

    def __init__(self, game: TCGGame, cards_per_combat: int = 3) -> None:
        self._game: Final[TCGGame] = game
        self._cards_per_combat: Final[int] = (
            cards_per_combat  # 每场战斗为每个角色生成的卡牌数（开发阶段固定值）
        )

    ####################################################################################################################################
    def _get_combat_actor_entities(self) -> List[Entity]:
        """返回当前战斗中所有存活、且已挂载 DeckComponent 的角色实体。"""
        return [
            entity
            for entity in self._game.get_group(
                Matcher(
                    ActorComponent,
                    DeckComponent,
                    DrawPileComponent,
                    CharacterStatsComponent,
                    KeywordComponent,
                )
            ).entities
            if not entity.has(DeathComponent)
        ]

    ####################################################################################################################################
    @override
    async def execute(self) -> None:
        dungeon = self._game.current_dungeon

        # 触发条件：战斗进行中且尚未创建任何回合（只触发一次）
        if not dungeon.is_ongoing:
            return
        current_rounds = dungeon.current_rounds
        if current_rounds is None or len(current_rounds) > 0:
            return

        actor_entities = self._get_combat_actor_entities()
        if not actor_entities:
            logger.warning("DeckGenerationSystem: 没有找到任何战斗角色实体，跳过")
            return

        logger.debug(
            f"DeckGenerationSystem: 为 {len(actor_entities)} 个角色生成初始牌库"
        )

        # 构建并行 LLM 请求
        chat_clients: List[DeepSeekClient] = []
        for entity in actor_entities:

            # 获取角色战斗属性
            num_cards = self._cards_per_combat

            # 获取角色关键词
            combat_stats = self._game.compute_character_stats(entity)

            keyword_comp = entity.get(KeywordComponent)
            keywords = keyword_comp.keywords if keyword_comp is not None else []
            sampled_keywords = _sample_keywords(keywords, k=num_cards)

            dice_rolls = [
                random.randint(DiceValue.MIN, DiceValue.MAX) for _ in range(num_cards)
            ]
            logger.debug(
                f"[{entity.name}] 关键词: {[k.description[:20] for k in sampled_keywords]}  骰值: {dice_rolls}"
            )

            prompt = _generate_deck_prompt(
                actor_stats=combat_stats,
                num_cards=num_cards,
                keywords=sampled_keywords,
                dice_rolls=dice_rolls,
            )

            chat_clients.append(
                DeepSeekClient(
                    name=entity.name,
                    prompt=prompt,
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

            self._process_generation_response(entity1, chat_client)

    #######################################################################################################################################
    def _process_generation_response(
        self,
        entity: Entity,
        chat_client: DeepSeekClient,
    ) -> None:
        """解析 LLM 响应，将生成卡牌洗牌填入 DrawPileComponent。解析失败时跳过（DrawPile 保持空）。"""

        # 获取预期生成卡牌数量
        num_cards = self._cards_per_combat

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
                        hit_count=entry.hit_count,
                        target_type=TargetType(entry.target_type),
                        source=entity.name,
                    )
                )

            if len(cards) != num_cards:
                logger.warning(
                    f"[{entity.name}] 牌库生成卡牌数量（{len(cards)}）与预期（{num_cards}）不符"
                )

            # 追加至 DeckComponent，洗牌后整体移入 DrawPileComponent
            deck_comp = entity.get(DeckComponent)
            assert deck_comp is not None, f"{entity.name} 缺少 DeckComponent"
            deck_comp.cards.extend(cards)

            # 洗牌
            random.shuffle(deck_comp.cards)

            # 移入 DrawPileComponent
            draw_pile = entity.get(DrawPileComponent)
            assert draw_pile is not None, f"{entity.name} 缺少 DrawPileComponent"
            draw_pile.cards.extend(deck_comp.cards)
            deck_comp.cards.clear()

            logger.debug(
                f"[{entity.name}] 牌库生成完成：{len(draw_pile.cards)} 张卡牌已洗牌填入 DrawPile"
                f"：{[c.name for c in draw_pile.cards]}"
            )

        except Exception as e:
            logger.error(
                f"DeckGenerationSystem 解析失败 [{entity.name}]: {e}\n{chat_client.response_content}"
            )
            # 解析失败：DrawPile 保持空，DrawCardsActionSystem 回合首次抽牌时会插入兜底牌
