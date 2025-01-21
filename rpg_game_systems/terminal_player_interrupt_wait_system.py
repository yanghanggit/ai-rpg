from entitas import ExecuteProcessor  # type: ignore
from typing import final, override
from game.rpg_game_context import RPGGameContext
from game.rpg_game import RPGGame
from game.terminal_rpg_game import TerminalRPGGame


@final
class TerminalPlayerInterruptWaitSystem(ExecuteProcessor):
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        if not isinstance(self._game, TerminalRPGGame):
            return

        while True:
            input(
                f"........请任意键继续........将要进入agent做计划的环节，因为会执行推理会有token的消耗，可以在这里停止程序"
            )
            break


############################################################################################################
