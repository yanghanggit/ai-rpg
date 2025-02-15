from entitas import ExecuteProcessor  # type: ignore
from typing import final, override, cast
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from loguru import logger


@final
class SaveSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    ############################################################################################################
    @override
    def execute(self) -> None:
        mapping = self._game.retrieve_stage_actor_mapping()
        logger.debug(f"mapping = {mapping}")
        self._game.save()

    ############################################################################################################
