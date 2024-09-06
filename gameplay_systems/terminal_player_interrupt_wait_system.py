from entitas import ExecuteProcessor  # type: ignore
from typing import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from rpg_game.terminal_game import TerminalGame


class TerminalPlayerInterruptWaitSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        if not isinstance(self._game, TerminalGame):
            return

        while True:
            input(f"........请任意键继续........")
            break


############################################################################################################
