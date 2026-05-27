"""
牌库归还系统模块
"""

from typing import Final, final, override
from loguru import logger
from ..entitas import ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    DeckComponent,
    DrawPileComponent,
    DiscardPileComponent,
    ExhaustPileComponent,
)


#######################################################################################################################################
@final
class DeckReturnSystem(ExecuteProcessor):
    """
    战斗结束后将三个战斗子堆的自有卡牌归还 DeckComponent，并清空子堆。
    """

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    async def execute(self) -> None:

        logger.debug("DeckReturnSystem: 执行牌库归还系统")

        dungeon = self._game.current_dungeon
        if not dungeon.is_post_combat:
            logger.debug("DeckReturnSystem: 当前非战斗后阶段，跳过牌库归还")
            return

        # 获取实体
        entities = list(
            self._game.get_group(
                Matcher(
                    ActorComponent,
                    DeckComponent,
                    DrawPileComponent,
                    DiscardPileComponent,
                    ExhaustPileComponent,
                )
            ).entities
        )

        if not entities:
            logger.debug("DeckReturnSystem: 没有符合条件的实体，跳过牌库归还")
            return

        logger.debug(f"DeckReturnSystem: 战斗结束，为 {len(entities)} 个实体归还牌库")

        for entity in entities:

            assert entity.has(
                DeckComponent
            ), "牌库归还系统中实体缺少 DeckComponent 组件！"
            deck_comp = entity.get(DeckComponent)

            assert entity.has(
                DrawPileComponent
            ), "牌库归还系统中实体缺少 DrawPileComponent 组件！"
            draw_pile = entity.get(DrawPileComponent)

            assert entity.has(
                DiscardPileComponent
            ), "牌库归还系统中实体缺少 DiscardPileComponent 组件！"
            discard_pile = entity.get(DiscardPileComponent)

            assert entity.has(
                ExhaustPileComponent
            ), "牌库归还系统中实体缺少 ExhaustPileComponent 组件！"
            exhaust_pile = entity.get(ExhaustPileComponent)

            # 收集三个战斗子堆中属于本角色的卡牌
            all_combat_cards = (
                list(draw_pile.cards)
                + list(discard_pile.cards)
                + list(exhaust_pile.cards)
            )

            # 通过 source 属性区分自有牌与外来牌（如其他角色丢弃的牌），确保只归还本角色的牌
            own_cards = [c for c in all_combat_cards if c.source == entity.name]

            # 记录外来牌数量（仅用于日志输出，实际不处理外来牌）
            foreign_dropped = [c for c in all_combat_cards if c.source != entity.name]

            # 归还自有牌至 DeckComponent
            deck_comp.cards.extend(own_cards)

            # 清空三个战斗子堆
            draw_pile.cards.clear()
            discard_pile.cards.clear()
            exhaust_pile.cards.clear()

            logger.debug(
                f"[{entity.name}] 归还 {len(own_cards)} 张自有牌至 DeckComponent"
                f"（丢弃 {len(foreign_dropped)} 张外来牌）"
                f"，DeckComponent 现有 {len(deck_comp.cards)} 张"
            )
