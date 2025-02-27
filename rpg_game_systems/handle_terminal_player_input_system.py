from entitas import ExecuteProcessor  # type: ignore
from typing import final, override
from game.rpg_game_context import RPGGameContext
from game.rpg_game import RPGGame
from components.components import PlanningFlagComponent
from loguru import logger
from game.terminal_rpg_game import TerminalRPGGame


############################################################################################################
@final
class HandleTerminalPlayerInputSystem(ExecuteProcessor):
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        if not isinstance(self._game, TerminalRPGGame):
            return

        for player_proxy in self._game.players:

            player_entity = self._context.get_player_entity(player_proxy.name)
            if player_entity is None:
                logger.warning(
                    f"player_entity is None, player_proxy.name={player_proxy.name}"
                )
                continue

            if not player_entity.has(PlanningFlagComponent):
                continue

            for command in player_proxy._commands:
                command.execute(self._game, player_proxy)

            player_proxy._commands.clear()


############################################################################################################
