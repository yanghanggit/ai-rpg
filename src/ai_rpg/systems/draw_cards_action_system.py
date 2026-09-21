"""
卡牌抽取系统模块
"""

import random
from typing import Final, List, final, override, Dict
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    DrawPileComponent,
    DiscardPileComponent,
    DrawCardsAction,
    HandComponent,
    Card,
    DeathComponent,
    CharacterStatsComponent,
    PartyMemberComponent,
)


#######################################################################################################################################
@final
class DrawCardsActionSystem(ReactiveProcessor):
    """
    响应 DrawCardsAction，为每个存活角色填充 HandComponent。
    先取回 retain 牌（原样保留在手牌），再额外从牌堆尝试抓取目标张数的新牌：
    retain 牌不占用抓牌名额，新抽牌与 retain 牌叠加，手牌总数可超过目标张数。
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
        assert (
            draw_pile is not None and discard_pile is not None
        ), "DrawPileComponent 或 DiscardPileComponent 不存在"

        drawn: List[Card] = []
        while len(drawn) < n:

            if draw_pile.cards:

                # DrawPile 非空，直接抽取一张牌
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

    ####################################################################################################################################
    def _take_retained_cards(self, entity: Entity) -> List[Card]:
        """取出 DrawPile.retained_cards 中的 retain 牌（FIFO 归还手牌）。"""
        draw_pile = entity.get(DrawPileComponent)
        assert draw_pile is not None

        retained = list(draw_pile.retained_cards)
        draw_pile.retained_cards.clear()
        return retained

    ####################################################################################################################################
    def _draw_target_count(self, entity: Entity) -> int:
        """每次尝试从牌堆抓取的目标张数（PartyMember 与非 PartyMember 均为 3 张）。"""
        return 3 if entity.has(PartyMemberComponent) else 3

    ######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，DrawCardsActionSystem 不执行")
            return

        # 状态守卫：本回合已抽牌 → 拒绝重复抽牌（一个回合每个存活参与者只能抓一次）
        last_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert last_round is not None, "DrawCardsActionSystem: 无法获取当前回合信息！"
        if last_round.draw_completed:
            logger.debug(
                f"DrawCardsActionSystem: 第 {len(self._game.current_dungeon_combat_room.combat.rounds)} 回合已抽牌，跳过重复抽牌"
            )
            return

        logger.debug(
            f"DrawCardsActionSystem: 处理 {len(entities)} 个实体的 DrawCardsAction"
        )

        # 先取回 retain 牌，再额外尝试抓取目标张数的新牌：
        # retain 牌不占用名额，只是原样留在手牌，新抽牌照常尽量抓满目标张数。
        for entity in entities:

            # 本次尝试抓取的目标张数
            draw_target_count = self._draw_target_count(entity)

            # 先取回 retain 牌（不占用抓牌名额，留在手牌）
            retained = self._take_retained_cards(entity)

            # 在 retain 牌之外，尽量抓满目标张数（牌堆不足则有多少抓多少）
            drawn = self._draw_from_pile(entity, draw_target_count)

            # 合并 retain 牌与新抽牌为新的手牌（总数可超过目标张数）
            new_hand = retained + drawn

            logger.debug(
                f"[{entity.name}] retain 牌 {len(retained)} 张 + 新抽 {len(drawn)} 张"
                f"（目标 {draw_target_count} 张）：{[c.name for c in drawn]} → 手牌共 {len(new_hand)} 张"
            )
            entity.replace(HandComponent, entity.name, new_hand)

        # 标记本回合 DRAW 阶段已完成
        last_round.draw_completed = True

    #######################################################################################################################################
