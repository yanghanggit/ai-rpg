from entitas import ExecuteProcessor  # type: ignore
from typing import final, override
from game.tcg_game import TCGGame
from loguru import logger
from game.web_tcg_game import WebTCGGame
from player.player_proxy import PlayerProxy
from player.player_command2 import PlayerCommand2


############################################################################################################
@final
class HandleWebPlayerInputSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:

        if not isinstance(self._game, WebTCGGame):
            return

        for command in self._game.player._commands2:
            self._execute_player_command(self._game.player, command)

        self._game.player._commands2.clear()

    ############################################################################################################
    def _execute_player_command(
        self, player_proxy: PlayerProxy, command: PlayerCommand2
    ) -> None:
        logger.debug(
            f"player = {player_proxy.name}, actor = {player_proxy.actor_name}, command = {command}"
        )


############################################################################################################
