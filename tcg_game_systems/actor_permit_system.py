from entitas import ExecuteProcessor, Entity  # type: ignore
from overrides import override
from typing import final, Set
from game.tcg_game import TCGGame
import random
from components.components_v_0_0_1 import (
    ActorComponent,
    ActorPermitComponent,
    EnterStageComponent,
    DungeonComponent,
)
from loguru import logger


#######################################################################################################################################
@final
class ActorPermitSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        current_stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert current_stage_entity is not None
        if current_stage_entity is None:
            return

        if current_stage_entity.has(DungeonComponent):
            return

        # 得到所有在玩家所在stage的actor
        actors = list(self._game.retrieve_stage_actor_mapping()[current_stage_entity])
        if len(actors) == 0:
            return

        if not player_entity.has(EnterStageComponent):
            # 随机选择一个actor
            random_actor = random.choice(actors)
            self._add_permit({random_actor})
        else:
            self._add_permit(set(actors))

    #######################################################################################################################################
    def _add_permit(self, entities: Set[Entity]) -> None:

        for entity in entities:
            entity.replace(
                ActorPermitComponent,
                entity.get(ActorComponent).name,
            )

    #######################################################################################################################################
