"""出牌前系统模块（队员）。"""

from typing import Final, List, final, Dict
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    PlayCardsAction,
    HandComponent,
    PartyMemberComponent,
    DeathComponent,
)


#######################################################################################################################################
@final
class PartyPrePlaySystem(ReactiveProcessor):
    """出牌前系统（队员）。预留 hook，供后续出牌前注入机制扩展，与 MonsterPrePlaySystem 结构对齐。"""

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlayCardsAction)
            and entity.has(HandComponent)
            and entity.has(PartyMemberComponent)
            and not entity.has(DeathComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("PartyPrePlaySystem: 战斗未进行中，跳过")
            return

        logger.debug(
            f"PartyPrePlaySystem: 触发出牌前处理，找到 {len(entities)} 个符合条件的出牌实体"
        )

    #######################################################################################################################################
