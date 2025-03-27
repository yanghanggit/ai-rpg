from typing import final
from game.tcg_game import TCGGame


@final
class TerminalTCGGame(TCGGame):
    run_home_once = False
