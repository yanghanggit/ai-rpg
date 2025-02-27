from entitas import ExecuteProcessor  # type: ignore
from typing import final, override, cast
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from game.terminal_tcg_game import TerminalTCGGame


@final
class TerminalPlayerInterruptWaitSystem(ExecuteProcessor):

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

        while True:
            input(
                f"........请任意键继续........将要进入agent做计划的环节，因为会执行推理会有token的消耗，可以在这里停止程序"
            )
            break


############################################################################################################
