from loguru import logger
from entitas import ExecuteProcessor, Matcher  # type: ignore
from overrides import override
from typing import cast, final
from components.components import (
    StageNarratePlanningPermitFlagComponent,
    StageComponent,
)

from game.tcg_game import TCGGame
from game.tcg_game_context import TCGGameContext


#######################################################################################################################################
@final
class StageNarratePlanningPermitSystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    #######################################################################################################################################
    @override
    def execute(self) -> None:

        # stage_entities = self._context.get_group(Matcher(StageComponent)).entities
        # for stage_entity in stage_entities:
        #     pass
        player_entity = self._game.get_player_entity()
        assert player_entity is not None
        player_stage = self._context.safe_get_stage_entity(player_entity)
        if player_stage is None:
            logger.error("Player stage is None")
            return
        player_stage.replace(
            StageNarratePlanningPermitFlagComponent,
            player_stage.get(StageComponent).name,
        )

    #######################################################################################################################################
