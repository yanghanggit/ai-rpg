from loguru import logger
from entitas import ExecuteProcessor  # type: ignore
from typing import final, override, cast
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from game.terminal_tcg_game import TerminalTCGGame
from player.player_command2 import PlayerCommand2


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

        # player_proxy = self._game._players[0]

        while True:
            usr_input = input(f"[{self._game.player.name}]:")
            if usr_input == "":
                logger.debug(f"玩家输入为空 = {self._game.player.name}，空跑一次")
                break

            if usr_input == "/quit" or usr_input == "/q":
                logger.info(f"玩家退出游戏 = {self._game.player.name}")
                self._game._will_exit = True
                break

            if usr_input == "/tp":
                player_entity = self._game.get_player_entity()
                assert player_entity is not None
                self._game.teleport_actors_to_stage({player_entity}, "场景.洞窟")
                continue

            self._game.player.add_command2(
                PlayerCommand2(user=self._game.player.name, command=usr_input)
            )


############################################################################################################
