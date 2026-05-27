"""消耗牌处理系统模块。

在 PlayCardsActionSystem 之后触发：检查刚出的牌是否为消耗牌（exhaust=True），
若是则将其从 DiscardPileComponent 移入 ExhaustPileComponent，
实现"出牌后永久消耗、不进入抽牌循环"的语义。
"""

from typing import Final, final

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
    """消耗牌处理系统。

    响应 PlayCardsAction 组件的添加事件（与 PlayCardsActionSystem 同触发时机，
    但在 pipeline 中位于其之后，保证 DiscardPile 已由 PlayCardsActionSystem 写入）。

    触发条件：
    - 实体添加 PlayCardsAction 组件
    - 战斗序列处于进行中（ongoing）状态

    执行流程：
    1. 读取 PlayCardsAction.card
    2. 若 card.exhaust == True 且 card.source == entity.name（自有牌）：
       - 用对象身份（is）从 DiscardPileComponent 找到该牌并移除
       - 将其追加到 ExhaustPileComponent
    3. 否则不做任何操作
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
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
    async def react(self, entities: list[Entity]) -> None:
        """处理消耗牌路由。

        将 exhaust=True 的自有牌从 DiscardPile 移至 ExhaustPile。
        """
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("ExhaustCardsActionSystem: 战斗未进行中，跳过消耗牌处理")
            return

        for entity in entities:
            play_cards_action = entity.get(PlayCardsAction)
            played_card = play_cards_action.card

            # 只处理消耗牌（exhaust=True）且来源为本角色的自有牌
            if not played_card.exhaust:
                continue
            
            # 
            if played_card.source != entity.name:
                logger.debug(
                    f"  [{entity.name}] 外来消耗牌 [{played_card.name}]"
                    f"(source={played_card.source!r}) 已由 PlayCardsActionSystem 静默丢弃，跳过"
                )
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
                # PlayCardsActionSystem 对自有牌必定写入 DiscardPile，此分支为防御性日志
                logger.warning(
                    f"  [{entity.name}] 消耗牌 [{played_card.name}] 未在 DiscardPile 中找到对应实例，跳过移入 ExhaustPile"
                )
