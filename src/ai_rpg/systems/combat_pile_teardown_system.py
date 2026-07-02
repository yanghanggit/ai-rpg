"""
战斗堆拆除系统模块
"""

from typing import Final, final, override
from loguru import logger
from ..entitas import ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    DeckComponent,
    DrawPileComponent,
    DiscardPileComponent,
    ExhaustPileComponent,
)


#######################################################################################################################################
@final
class CombatPileTeardownSystem(ExecuteProcessor):
    """
    战斗结束后清空并移除三个战斗临时子堆组件。
    """

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    async def execute(self) -> None:

        logger.debug("CombatPileTeardownSystem: 执行战斗堆拆除系统")

        dungeon = self._game.current_dungeon
        if not dungeon.is_post_combat:
            logger.debug("CombatPileTeardownSystem: 当前非战斗后阶段，跳过")
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
            logger.debug("CombatPileTeardownSystem: 没有符合条件的实体，跳过")
            return

        logger.debug(f"CombatPileTeardownSystem: 清理 {len(entities)} 个实体的战斗子堆")

        for entity in entities:

            draw_pile = entity.get(DrawPileComponent)
            discard_pile = entity.get(DiscardPileComponent)
            exhaust_pile = entity.get(ExhaustPileComponent)

            total = (
                len(draw_pile.cards) + len(discard_pile.cards) + len(exhaust_pile.cards)
            )

            # 清空三个战斗子堆（副本直接丢弃，原始牌在 DeckComponent 中完整保留）
            draw_pile.cards.clear()
            discard_pile.cards.clear()
            exhaust_pile.cards.clear()

            # 移除战斗临时组件
            entity.remove(DrawPileComponent)
            entity.remove(DiscardPileComponent)
            entity.remove(ExhaustPileComponent)

            deck_comp = entity.get(DeckComponent)
            logger.debug(
                f"[{entity.name}] 战斗子堆已清理（丢弃 {total} 张副本）"
                f"，DeckComponent 原始牌库保留 {len(deck_comp.cards)} 张"
            )
