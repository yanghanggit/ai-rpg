import datetime
from typing import Optional

from ..game.web_tcg_game import WebTCGGame


class Room:

    def __init__(self, user_name: str) -> None:
        self._user_name = user_name
        self._game: Optional[WebTCGGame] = None
        self._last_access_time: datetime.datetime = datetime.datetime.now()

    ###############################################################################################################################################
    @property
    def game(self) -> Optional[WebTCGGame]:
        self._update_access_time()
        return self._game

    ###############################################################################################################################################
    @game.setter
    def game(self, game: WebTCGGame) -> None:
        self._game = game
        self._update_access_time()

    ###############################################################################################################################################
    def _update_access_time(self) -> None:
        self._last_access_time = datetime.datetime.now()

    ###############################################################################################################################################
    @property
    def last_access_time(self) -> datetime.datetime:
        return self._last_access_time

    ###############################################################################################################################################
