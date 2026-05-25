"""
牌库归还系统模块

在战斗结束后（is_post_combat）将所有战斗牌堆（DrawPile、DiscardPile、ExhaustPile）
中属于各角色自身的卡牌归还至其 DeckComponent，并清空三个战斗子堆。

主要组件：
- DeckReturnSystem: 核心系统类（ExecuteProcessor）
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

    触发条件：is_post_combat == True

    注意：CombatArchiveSystem 在本系统之前运行并调用 transition_to_post_combat()，
    因此本系统必须在 is_post_combat（state==POST_COMBAT）时触发，
    而非 is_combat_completed（state==COMPLETE）。

    适用于所有挂载 DeckComponent 的实体（玩家、盟友、怪物均走相同流程）。
    怪物实体在 DeckReturnSystem 执行后由外部服务统一销毁，顺序安全。
    """

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    async def execute(self) -> None:
        dungeon = self._game.current_dungeon

        if not dungeon.is_post_combat:
            return

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
            return

        logger.debug(f"DeckReturnSystem: 战斗结束，为 {len(entities)} 个实体归还牌库")

        for entity in entities:
            deck_comp = entity.get(DeckComponent)
            draw_pile = entity.get(DrawPileComponent)
            discard_pile = entity.get(DiscardPileComponent)
            exhaust_pile = entity.get(ExhaustPileComponent)

            assert deck_comp is not None
            assert draw_pile is not None
            assert discard_pile is not None
            assert exhaust_pile is not None

            # 收集三个战斗子堆中属于本角色的卡牌
            all_combat_cards = (
                list(draw_pile.cards)
                + list(discard_pile.cards)
                + list(exhaust_pile.cards)
            )
            own_cards = [c for c in all_combat_cards if c.source == entity.name]
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
