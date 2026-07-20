"""
卡牌抽取系统模块
"""

import random
from typing import Final, List, final, override, Dict
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import get_max_num_cards
from ..models import (
    ActorComponent,
    DrawPileComponent,
    DiscardPileComponent,
    DrawCardsAction,
    HandComponent,
    Card,
    DeathComponent,
    CharacterStatsComponent,
)


#######################################################################################################################################
@final
class DrawCardsActionSystem(ReactiveProcessor):
    """
    响应 DrawCardsAction，为每个存活角色填充 HandComponent。
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
                logger.warning(f"[{entity.name}] DrawPile 与 DiscardPile 均空")
                break

        return drawn

    ######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_combat_room.combat.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，DrawCardsActionSystem 不执行")
            return

        logger.debug(
            f"DrawCardsActionSystem: 处理 {len(entities)} 个实体的 DrawCardsAction"
        )

        # 从 DrawPile 抽牌（含 DiscardPile reshuffle 逻辑），并立即写入原始（未调整）手牌
        for entity in entities:
            drawn = self._draw_from_pile(entity, get_max_num_cards(entity))
            logger.debug(
                f"[{entity.name}] 抽取 {len(drawn)} 张：{[c.name for c in drawn]}"
            )
            entity.replace(HandComponent, entity.name, drawn)

    #######################################################################################################################################
