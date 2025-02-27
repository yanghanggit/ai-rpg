from entitas import ExecuteProcessor  # type: ignore
from typing import final, override, cast
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from loguru import logger
from game.terminal_tcg_game import TerminalTCGGame
from player.player_proxy import PlayerProxy
from player.player_command2 import PlayerCommand2


############################################################################################################
@final
class HandleTerminalPlayerInputSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    ############################################################################################################
    @override
    def execute(self) -> None:

        if not isinstance(self._game, TerminalTCGGame):
            return

        # for player_proxy in self._game.players:

        # player_entity = self._context.get_player_entity(self._game.player.player_name)
        # if player_entity is None:
        #     logger.warning(
        #         f"player_entity is None, player_proxy.name={self._game.player.player_name}"
        #     )
        #     return

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
