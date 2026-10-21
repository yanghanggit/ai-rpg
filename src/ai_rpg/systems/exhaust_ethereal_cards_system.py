"""虚无牌处理系统模块：pass turn 时，将仍在手牌中的 ethereal=True 牌自动移入 ExhaustPile。"""

from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    ExhaustPileComponent,
    HandComponent,
    PassTurnAction,
)
from .card_pile_common import (
    PILE_EXHAUST,
    PILE_HAND,
    format_card_names,
    record_pile_change,
)


#######################################################################################################################################
@final
class ExhaustEtherealCardsSystem(ReactiveProcessor):
    """虚无牌自动消耗系统：响应 PassTurnAction，将手牌中 ethereal=True 的牌移入 ExhaustPile。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PassTurnAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PassTurnAction)
            and entity.has(ActorComponent)
            and entity.has(HandComponent)
            and entity.has(ExhaustPileComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        """pass turn 时，将仍在手牌中的虚无牌移入 ExhaustPile。"""

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("ExhaustEtherealCardsSystem: 战斗未进行中，跳过虚无牌处理")
            return

        for entity in entities:
            hand_comp = entity.get(HandComponent)
            exhaust_pile = entity.get(ExhaustPileComponent)

            # 找出手牌中所有虚无牌（ethereal=True）
            ethereal_cards = [c for c in hand_comp.cards if c.ethereal]
            if not ethereal_cards:
                continue

            # 将手牌中所有虚无牌移入 ExhaustPile
            new_hand = [c for c in hand_comp.cards if not c.ethereal]
            new_exhaust = [*exhaust_pile.cards, *ethereal_cards]
            entity.replace(HandComponent, hand_comp.name, new_hand)
            entity.replace(ExhaustPileComponent, exhaust_pile.name, new_exhaust)

            # 虚无牌在回合末自行消散：主人必须知道哪些牌没了、去了哪里
            record_pile_change(
                self._game,
                entity,
                change="exhaust_ethereal",
                title="虚无牌消散",
                lines=[
                    f"回合结束时仍在手牌的 {format_card_names(ethereal_cards)}消散了，进入消耗堆（本场不再回来）。",
                    f"手牌 {len(new_hand)} 张，消耗堆 {len(new_exhaust)} 张。",
                ],
                deltas={
                    PILE_HAND: -len(ethereal_cards),
                    PILE_EXHAUST: len(ethereal_cards),
                },
            )

            logger.debug(
                f"  [{entity.name}] pass turn 自动消耗 {len(ethereal_cards)} 张虚无牌：{[c.name for c in ethereal_cards]}（ExhaustPile 累计 {len(new_exhaust)} 张）"
            )
