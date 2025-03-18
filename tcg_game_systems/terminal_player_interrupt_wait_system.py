from entitas import ExecuteProcessor  # type: ignore
from typing import final, override
from game.tcg_game_context import TCGGameContext

# from game.tcg_game import TCGGame
from game.terminal_tcg_game import TerminalTCGGame


@final
class TerminalPlayerInterruptWaitSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, context: TCGGameContext) -> None:
        self._game: TCGGameContext = context
        # self._game: TCGGame = cast(TCGGame, context._game)
        # assert self._game is not None

    ############################################################################################################
    @override
    def execute(self) -> None:

        if not isinstance(self._game, TerminalTCGGame):
            return

        while True:
            input(f"！！！！！打断调试！！！........请任意键继续........")
            break


############################################################################################################
