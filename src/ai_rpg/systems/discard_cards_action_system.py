"""弃牌处理系统：回合结束时非保留手牌进弃牌堆。"""

from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    DiscardPileComponent,
    HandComponent,
    PlayCardsAction,
)
from .card_pile_common import PILE_DISCARD, PILE_HAND, record_pile_change


#######################################################################################################################################
@final
class DiscardCardsActionSystem(ReactiveProcessor):
    """弃牌处理系统。"""

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
            and entity.has(HandComponent)
            and entity.has(DiscardPileComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        """将出牌从 Hand 移入 DiscardPile。"""
        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("DiscardCardsActionSystem: 战斗未进行中，跳过弃牌处理")
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

            # 出牌是决策，牌现在躺在哪是事实：事实由本系统记录。
            # 消耗牌的去向由 ExhaustCardsActionSystem 记录（它随后把这张牌移走），
            # 这里也跟着写会变成「先进弃牌堆、再进消耗堆」的自相矛盾记录。
            if not played_card.exhaust:
                record_pile_change(
                    self._game,
                    entity,
                    change="play_to_discard",
                    title="出牌结算 · 弃牌",
                    lines=[
                        f"「{played_card.name}」离开手牌进入弃牌堆。",
                        f"手牌 {len(hand_comp.cards)} 张，"
                        f"弃牌堆 {len(discard_pile.cards)} 张。",
                    ],
                    deltas={
                        PILE_HAND: len(hand_comp.cards) - before_count,
                        PILE_DISCARD: 1,
                    },
                )

            logger.debug(
                f"  [{entity.name}] 手牌 {before_count} → {len(hand_comp.cards)}，"
                f"DiscardPile 累计 {len(discard_pile.cards)} 张"
                f"（牌：{played_card.name}，source={played_card.source!r}）"
            )
