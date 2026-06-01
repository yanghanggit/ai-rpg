"""出牌后路由系统模块。"""

from typing import Final, final, Dict, List
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    ActorComponent,
    DiscardPileComponent,
    HandComponent,
    PlayCardsAction,
)
from ..game.tcg_game import TCGGame


#######################################################################################################################################
@final
class MoveToDiscardPileSystem(ReactiveProcessor):
    """出牌后路由系统。"""

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlayCardsAction)
            and entity.has(ActorComponent)
            and entity.has(HandComponent)
            and entity.has(DiscardPileComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        """将出牌从 Hand 移入 DiscardPile。"""
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("MoveToDiscardPileSystem: 战斗未进行中，跳过出牌路由")
            return

        for entity in entities:
            play_cards_action = entity.get(PlayCardsAction)
            played_card = play_cards_action.card

            hand_comp = entity.get(HandComponent)
            discard_pile = entity.get(DiscardPileComponent)

            # 用对象身份（is）移除，确保只移除本次出的那一张实例
            before_count = len(hand_comp.cards)
            hand_comp.cards = [c for c in hand_comp.cards if c is not played_card]

            discard_pile.cards.append(played_card)

            logger.debug(
                f"  [{entity.name}] 手牌 {before_count} → {len(hand_comp.cards)}，"
                f"DiscardPile 累计 {len(discard_pile.cards)} 张"
                f"（牌：{played_card.name}，source={played_card.source!r}）"
            )
