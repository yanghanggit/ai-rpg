from entitas import ExecuteProcessor  # type: ignore
from overrides import override
from typing import final, cast
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from loguru import logger


#######################################################################################################################################
@final
class WorldSystemPlanningSystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        logger.debug("WorldSystemPlanningExecutionSystem.execute()")

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:
        logger.debug("WorldSystemPlanningExecutionSystem.a_execute1()")

    #######################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        logger.debug("WorldSystemPlanningExecutionSystem.a_execute2()")

    #######################################################################################################################################
