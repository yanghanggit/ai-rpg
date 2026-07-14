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
from ..game.dbg_game import DBGGame


#######################################################################################################################################
@final
class ExhaustCardsActionSystem(ReactiveProcessor):
    """消耗牌处理系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

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
        if not self._game.current_combat_room.combat.is_ongoing:
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

            # MoveToDiscardPileSystem 先执行，已将还原后的原始牌（与 played_card 同 uuid）写入 DiscardPile
            # 通过 uuid 定位（played_card 本身是调整副本，不在 DiscardPile 中）
            card_to_exhaust = next(
                (c for c in discard_pile.cards if c.uuid == played_card.uuid),
                None,
            )

            if card_to_exhaust is not None:
                discard_pile.cards = [
                    c for c in discard_pile.cards if c.uuid != played_card.uuid
                ]
                exhaust_pile.cards.append(card_to_exhaust)
                logger.debug(
                    f"  [{entity.name}] 消耗牌 [{played_card.name}] 已从 DiscardPile 移入 ExhaustPile"
                    f"（ExhaustPile 累计 {len(exhaust_pile.cards)} 张）"
                )
            else:
                # MoveToDiscardPileSystem 对所有出牌必定写入 DiscardPile，此分支为防御性日志
                logger.warning(
                    f"  [{entity.name}] 消耗牌 [{played_card.name}] 未在 DiscardPile 中找到对应实例，跳过移入 ExhaustPile"
                )
