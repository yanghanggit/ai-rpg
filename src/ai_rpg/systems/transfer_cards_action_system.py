"""可传递卡牌转移系统模块。"""

from typing import Dict, Final, List, final
from uuid import uuid4

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    DeathComponent,
    HandComponent,
    PlayCardsAction,
)


#######################################################################################################################################
@final
class TransferCardsActionSystem(ReactiveProcessor):
    """可传递卡牌转移系统。

    响应 PlayCardsAction 事件：把 transferable=True 的卡牌本体从出牌者手牌移除，
    并为每个存活目标的手牌 copy 一份（副本 uuid 重新生成，source 保持原来源）。
    """

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
            and entity.has(HandComponent)
            and entity.has(ActorComponent)
            and entity.get(PlayCardsAction).card.transferable
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        """将可传递卡牌从源手牌移除，并 copy 到每个目标手牌。"""
        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("TransferCardsActionSystem: 战斗未进行中，跳过卡牌转移")
            return

        for entity in entities:
            play_cards_action = entity.get(PlayCardsAction)
            card = play_cards_action.card
            source_hand = entity.get(HandComponent)

            # 从源手牌移除本体（原卡后续由 DiscardCardsActionSystem 归入弃牌堆）。
            source_hand.cards = [c for c in source_hand.cards if c is not card]

            # 目标去重后，为每个存活且拥有手牌的目标 copy 一份（新 uuid）。
            for target_name in dict.fromkeys(play_cards_action.targets):
                target = self._game.get_actor_entity(target_name)
                if (
                    target is None
                    or target.has(DeathComponent)
                    or not target.has(HandComponent)
                ):
                    continue

                copied = card.model_copy(deep=True)
                copied.uuid = str(uuid4())
                target.get(HandComponent).cards.append(copied)
                logger.debug(
                    f"transfer_card: 「{card.name}」已 copy 到 {target_name} 的手牌"
                    f"（source={copied.source!r}，新 uuid={copied.uuid}）"
                )
