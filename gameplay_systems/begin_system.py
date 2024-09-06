from entitas import InitializeProcessor, ExecuteProcessor  # type: ignore
from typing import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from rpg_game.rpg_game import RPGGame


class BeginSystem(InitializeProcessor, ExecuteProcessor):
    ############################################################################################################
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def initialize(self) -> None:
        pass

    ############################################################################################################
    @override
    def execute(self) -> None:

        self._game._round += 1
        logger.debug(f"self._context._execute_count = {self._game._round}")

        self._context._round_messages = {}


############################################################################################################
