from entitas import ExecuteProcessor  # type: ignore
from typing import final, override, cast
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from loguru import logger


@final
class BeginSystem(ExecuteProcessor):
    ############################################################################################################
    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)

    ############################################################################################################
    @override
    def execute(self) -> None:
        logger.info("BeginSystem execute")
