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
    """可传递卡牌转移系统。"""

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
                assert target is not None, f"目标 {target_name} 不存在"
                assert target.has(HandComponent), f"目标 {target_name} 不存在手牌组件"
                assert not target.has(DeathComponent), f"目标 {target_name} 已死亡"
                # if (
                #     target is None
                #     or target.has(DeathComponent)
                #     or not target.has(HandComponent)
                # ):
                #     continue

                if target_name == play_cards_action.name:
                    # 跳过将卡牌传递给自己
                    logger.debug(
                        f"transfer_card: 跳过将卡牌传递给自己（{target_name}）？这是什么打法？故意复制牌的？"
                    )

                # 将卡牌 copy 到目标手牌
                copied = card.model_copy(deep=True)
                copied.uuid = str(uuid4())
                target.get(HandComponent).cards.append(copied)
                logger.debug(
                    f"transfer_card: 「{card.name}」已 copy 到 {target_name} 的手牌"
                    f"（source={copied.source!r}，新 uuid={copied.uuid}）"
                )
