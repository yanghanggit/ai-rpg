from entitas import ExecuteProcessor, Entity  # type: ignore
from overrides import override
from typing import final, Set
from game.tcg_game import TCGGame
import random
from components.components import (
    ActorComponent,
    ActorRolePlayPlanningPermitFlagComponent,
)
from loguru import logger


#######################################################################################################################################
@final
class ActorRoleplayPlanningPermitSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        player_entity = self._game.get_player_entity()
        assert player_entity is not None
        player_stage = self._game.safe_get_stage_entity(player_entity)
        if player_stage is None:
            logger.error("Player stage is None")
            return
        # 得到所有在玩家所在stage的actor
        actors = list(self._game.retrieve_stage_actor_mapping()[player_stage])
        if len(actors) == 0:
            return

        # 随机选择一个actor
        random_actor = random.choice(actors)
        self._add_permit({random_actor})

    #######################################################################################################################################
    def _add_permit(self, entities: Set[Entity]) -> None:
        for entity in entities:
            entity.replace(
                ActorRolePlayPlanningPermitFlagComponent,
                entity.get(ActorComponent).name,
            )

    #######################################################################################################################################
