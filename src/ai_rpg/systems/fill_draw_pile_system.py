"""抽牌堆填充系统：从 DeckComponent 洗牌填入 DrawPileComponent（零 LLM 调用）。"""

import random
from typing import Dict, Final, List, final, override

from loguru import logger

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_stats,
)
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    Card,
    DeathComponent,
    DeckComponent,
    DrawPileComponent,
    FillDrawPileAction,
    apply_stats_to_card,
)
from .card_pile_common import PILE_DRAW, record_pile_change


#######################################################################################################################################
@final
class FillDrawPileSystem(ReactiveProcessor):
    """响应 FillDrawPileAction，从 DeckComponent 填充 DrawPileComponent。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(FillDrawPileAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(FillDrawPileAction)
            and entity.has(ActorComponent)
            and entity.has(DeckComponent)
            and entity.has(DrawPileComponent)
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in entities:
            self._fill_draw_pile(entity)

    ####################################################################################################################################
    def _fill_draw_pile(self, entity: Entity) -> None:
        """将 DeckComponent 中的卡牌深拷贝、叠加角色属性后填入 DrawPileComponent。"""

        deck_comp = entity.get(DeckComponent)
        assert deck_comp is not None, f"[{entity.name}] 缺失 DeckComponent"

        draw_pile = entity.get(DrawPileComponent)
        assert draw_pile is not None, f"[{entity.name}] 缺失 DrawPileComponent"

        assert deck_comp.cards, (
            f"[{entity.name}] DeckComponent 为空：参战角色必须有可用牌库，"
            "空牌库属于数据损坏，不做降级"
        )

        cards = deck_comp.cards.copy()
        random.shuffle(cards)

        # 计算角色属性，用于叠加到卡牌上
        actor_stats = compute_character_stats(entity)

        adjusted_cards: List[Card] = []
        for card in cards:

            # 深拷贝：确保战斗内对卡牌的任意修改（含 on_play_affixes 嵌套列表）
            # 都不会反噬 DeckComponent 中的原始牌，战斗结束后原始牌库仍可安全保存。
            copied = card.model_copy(deep=True)

            # 属性叠加（加法）：卡牌自身值非 0 时，叠加角色基础属性。
            apply_stats_to_card(copied, actor_stats)

            adjusted_cards.append(copied)

        deck_size = len(deck_comp.cards)
        draw_before = len(draw_pile.cards)
        draw_pile.cards = adjusted_cards

        # 抽牌堆被重建：把「牌库 → 抽牌堆」的搬家告诉主人
        record_pile_change(
            self._game,
            entity,
            change="fill_draw_pile",
            title="牌库已洗入抽牌堆",
            lines=[
                f"牌库 {deck_size} 张洗牌后进入抽牌堆（你的属性已叠加到副本上）。",
                f"抽牌堆 {len(adjusted_cards)} 张，牌库 {deck_size} 张。",
            ],
            deltas={PILE_DRAW: len(adjusted_cards) - draw_before},
        )

        logger.debug(
            f"[{entity.name}] FillDrawPile: {len(adjusted_cards)} 张牌已洗牌"
            f"并叠加角色属性后填入 DrawPile"
        )
