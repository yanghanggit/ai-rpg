from game.tcg_game import TCGGame
from typing import final


@final
class WebTCGGame(TCGGame):
    is_game_started: bool = False
