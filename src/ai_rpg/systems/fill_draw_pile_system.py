"""抽牌堆填充系统：从 DeckComponent 洗牌填入 DrawPileComponent（零 LLM 调用）。"""

import random
from typing import Dict, Final, List, final, override
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    DeckComponent,
    DrawPileComponent,
    GenerateDeckAction,
    DeathComponent,
)


#######################################################################################################################################
@final
class FillDrawPileSystem(ReactiveProcessor):
    """响应 GenerateDeckAction，从 DeckComponent 填充 DrawPileComponent。"""

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
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in entities:
            self._fill_draw_pile(entity)

    ####################################################################################################################################
    def _fill_draw_pile(self, entity: Entity) -> None:
        """将 DeckComponent 中的卡牌洗牌后填入 DrawPileComponent。"""
        deck_comp = entity.get(DeckComponent)
        assert deck_comp is not None

        draw_pile = entity.get(DrawPileComponent)
        assert draw_pile is not None

        if not deck_comp.cards:
            logger.warning(f"[{entity.name}] DeckComponent 为空，无法填充 DrawPile")
            return

        cards = deck_comp.cards.copy()
        random.shuffle(cards)
        draw_pile.cards = [c.model_copy() for c in cards]

        logger.debug(
            f"[{entity.name}] FillDrawPile: {len(cards)} 张牌已洗牌填入 DrawPile"
        )
