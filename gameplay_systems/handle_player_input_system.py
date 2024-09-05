from entitas import ExecuteProcessor  # type: ignore
from typing import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from rpg_game.rpg_entitas_context import RPGEntitasContext


############################################################################################################
class HandlePlayerInputSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        for player_proxy in self._game.players:

            player_commands = player_proxy._commands
            for command in player_commands:
                command.execute(self._game, player_proxy)
            player_proxy._commands.clear()


############################################################################################################
