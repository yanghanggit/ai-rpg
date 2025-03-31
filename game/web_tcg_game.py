from game.tcg_game import TCGGame
from typing import final


@final
class WebTCGGame(TCGGame):
    start: bool = False
