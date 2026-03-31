from typing import Final, final, override
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    PlayCardsAction,
    EnemyComponent,
    DeathComponent,
    HandComponent,
)


#######################################################################################################################################
@final
class EnemyPlayDecisionSystem(ReactiveProcessor):

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
        """只处理敌人实体且未死亡的情况"""
        return (
            entity.has(PlayCardsAction)
            and entity.has(HandComponent)
            and entity.has(EnemyComponent)
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        # 验证战斗状态
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("EnemyDrawDecisionSystem: 战斗未进行中，跳过决策")
            return

    ####################################################################################################################################
