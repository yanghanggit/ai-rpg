from typing import Final, Optional
from ..game.web_tcg_game import WebTCGGame
from ..game.player_client import PlayerClient


class Room:

    def __init__(self, username: str) -> None:
        self._username: Final[str] = username
        self._game: Optional[WebTCGGame] = None
        self._player_client: Optional[PlayerClient] = None
