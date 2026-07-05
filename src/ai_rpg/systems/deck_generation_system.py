"""
牌库生成系统模块
"""

import random
from enum import IntEnum, unique
from typing import Dict, Final, List, final, override
from loguru import logger
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_entity_ops import compute_character_stats
from ..models import (
    ActorComponent,
    DeckComponent,
    DrawPileComponent,
    DeathComponent,
    HumanMessage,
    GenerateDeckAction,
    CharacterStatsComponent,
    Card,
    TargetType,
)
from ..utils import extract_json_from_code_block
from .card_prompt_builders import (
    DeckGenerateResponse,
    generate_deck_prompt,
    generate_compressed_deck_prompt,
)


###############################################################################################################################################
@final
@unique
class DiceValue(IntEnum):
    """骰值范围常量（0-100 均匀随机整数）"""

    MIN = 0
    MAX = 100


#######################################################################################################################################
def _sample_keywords(keywords: List[str], k: int) -> List[str]:
    """从关键词池中采样 k 个关键词，优先不重复，池不足时降级为有放回采样。"""
    if not keywords:
        return []
    if len(keywords) >= k:
        return random.sample(keywords, k=k)
    return random.choices(keywords, k=k)


#######################################################################################################################################
@final
class DeckGenerationSystem(ReactiveProcessor):
    """
    响应 GenerateDeckAction，为每个触发角色并行调用 LLM 生成初始牌库卡牌，
    """

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

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
            client, num_cards = self._build_deck_chat_client(entity)
            num_cards_map[entity.name] = num_cards
            chat_clients.append(client)

        await DeepSeekClient.batch_chat(clients=chat_clients)

        # 解析结果，填入 DeckComponent 后洗牌移入 DrawPileComponent
        for chat_client in chat_clients:
            self._process_generation_response(
                chat_client, num_cards_map[chat_client.name]
            )

    #######################################################################################################################################
    def _build_deck_chat_client(self, entity: Entity) -> tuple[DeepSeekClient, int]:
        """为单个实体构建牌库生成的 DeepSeekClient，同时返回本次目标卡牌数。"""
        generate_deck_action = entity.get(GenerateDeckAction)
        assert generate_deck_action is not None
        num_cards = generate_deck_action.num_cards

        combat_stats = compute_character_stats(entity)

        deck_comp_for_keywords = entity.get(DeckComponent)
        assert deck_comp_for_keywords is not None
        sampled_keywords = _sample_keywords(
            deck_comp_for_keywords.keywords, k=num_cards
        )

        dice_rolls = [
            random.randint(DiceValue.MIN, DiceValue.MAX) for _ in range(num_cards)
        ]
        logger.debug(
            f"[{entity.name}] 关键词: {[k[:20] for k in sampled_keywords]}  骰值: {dice_rolls}"
        )

        prompt = generate_deck_prompt(
            actor_stats=combat_stats,
            num_cards=num_cards,
            keywords=sampled_keywords,
            dice_rolls=dice_rolls,
        )
        compressed_prompt = generate_compressed_deck_prompt(
            actor_stats=combat_stats,
            num_cards=num_cards,
            keywords=sampled_keywords,
            dice_rolls=dice_rolls,
        )

        client = DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            compressed_prompt=compressed_prompt,
            context=self._game.get_agent_context(entity).context,
        )
        return client, num_cards

    #######################################################################################################################################
    def _process_generation_response(
        self,
        chat_client: DeepSeekClient,
        num_cards: int,
    ) -> None:
        """解析 LLM 响应，将生成卡牌洗牌填入 DrawPileComponent。解析失败时跳过（DrawPile 保持空）。"""

        entity = self._game.get_entity_by_name(chat_client.name)
        assert (
            entity is not None
        ), f"DeckGenerationSystem: 无法找到实体 {chat_client.name} 以处理生成结果"

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
                        entity=entity, human_message=HumanMessage(content=warn_msg)
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
                human_message=HumanMessage(
                    content=chat_client.compressed_prompt,
                    deck_generation_full_prompt=chat_client.prompt,
                ),
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
