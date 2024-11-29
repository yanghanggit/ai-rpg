from entitas import ExecuteProcessor  # type: ignore
from typing import final, override
from game.rpg_entitas_context import RPGEntitasContext
from game.rpg_game import RPGGame
from game.terminal_game import TerminalGame


@final
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
            input(
                f"........请任意键继续........将要进入agent做计划的环节，因为会执行推理会有token的消耗，可以在这里停止程序"
            )
            break


############################################################################################################
