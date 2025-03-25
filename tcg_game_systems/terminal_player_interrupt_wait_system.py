from entitas import ExecuteProcessor  # type: ignore
from typing import final, override
from game.tcg_game import TCGGame
from game.terminal_tcg_game import TerminalTCGGame


@final
class TerminalPlayerInterruptWaitSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:

        if not isinstance(self._game, TerminalTCGGame):
            return

        while True:
            input(
                f"！！！！！TerminalTCGGame 打断调试！！！........请任意键继续........"
            )
            break


############################################################################################################
