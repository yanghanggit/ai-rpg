"""消耗牌处理系统模块。"""

from typing import Final, final, Dict, List

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    ActorComponent,
    DiscardPileComponent,
    ExhaustPileComponent,
    PlayCardsAction,
)
from ..game.tcg_game import TCGGame


#######################################################################################################################################
@final
class ExhaustCardsActionSystem(ReactiveProcessor):
    """消耗牌处理系统。"""

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
            and entity.has(DiscardPileComponent)
            and entity.has(ExhaustPileComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        """处理消耗牌路由。

        将 exhaust=True 的自有牌从 DiscardPile 移至 ExhaustPile。
        """
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("ExhaustCardsActionSystem: 战斗未进行中，跳过消耗牌处理")
            return

        for entity in entities:
            play_cards_action = entity.get(PlayCardsAction)
            played_card = play_cards_action.card

            # 只处理消耗牌（exhaust=True）；战斗结束后由 CombatPileTeardownSystem 统一清理子堆
            if not played_card.exhaust:
                continue

            discard_pile = entity.get(DiscardPileComponent)
            exhaust_pile = entity.get(ExhaustPileComponent)

            # 用对象身份（is）定位，确保移除的是同一实例
            before_len = len(discard_pile.cards)
            discard_pile.cards = [c for c in discard_pile.cards if c is not played_card]

            if len(discard_pile.cards) < before_len:
                exhaust_pile.cards.append(played_card)
                logger.debug(
                    f"  [{entity.name}] 消耗牌 [{played_card.name}] 已从 DiscardPile 移入 ExhaustPile"
                    f"（ExhaustPile 累计 {len(exhaust_pile.cards)} 张）"
                )
            else:
                # MoveToDiscardPileSystem 对所有出牌必定写入 DiscardPile，此分支为防御性日志
                logger.warning(
                    f"  [{entity.name}] 消耗牌 [{played_card.name}] 未在 DiscardPile 中找到对应实例，跳过移入 ExhaustPile"
                )
