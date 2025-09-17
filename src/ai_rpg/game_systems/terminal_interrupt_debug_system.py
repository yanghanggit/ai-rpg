from typing import final, override
from loguru import logger
from ..entitas import ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..game.terminal_tcg_game import TerminalTCGGame


@final
class TerminalInterruptDebugSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    async def execute(self) -> None:

        if not isinstance(self._game, TerminalTCGGame):
            return

        while True:
            user_input = input(
                f"！！！！！TerminalTCGGame 打断调试！！！........请任意键继续........"
            )

            if user_input == "test":
                logger.warning("随便测试点啥啥啥，例如直接给agent一段消息之类的。")
                break

            break


############################################################################################################
