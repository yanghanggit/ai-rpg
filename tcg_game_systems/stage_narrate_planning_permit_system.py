from loguru import logger
from entitas import ExecuteProcessor  # type: ignore
from overrides import override
from typing import final
from components.components import (
    StageNarratePlanningPermitFlagComponent,
    StageComponent,
)

from game.tcg_game import TCGGame


#######################################################################################################################################
@final
class StageNarratePlanningPermitSystem(ExecuteProcessor):

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
        player_stage.replace(
            StageNarratePlanningPermitFlagComponent,
            player_stage.get(StageComponent).name,
        )

    #######################################################################################################################################
