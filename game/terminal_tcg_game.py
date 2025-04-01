from typing import final
from game.tcg_game import TCGGame


@final
class TerminalTCGGame(TCGGame):
    is_game_started = False
