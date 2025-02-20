from typing import Optional
from game.web_tcg_game import WebTCGGame


class Room:

    def __init__(self, user_name: str) -> None:
        self._user_name = user_name
        self._game: Optional[WebTCGGame] = None

    ###############################################################################################################################################
    @property
    def game(self) -> Optional[WebTCGGame]:
        return self._game

    ###############################################################################################################################################
