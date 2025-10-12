from typing import Final, Optional
from ..game.tcg_game import TCGGame
from ..game.player_client import PlayerClient


class Room:

    def __init__(self, username: str) -> None:
        self._username: Final[str] = username
        self._game: Optional[TCGGame] = None
        self._player_client: Optional[PlayerClient] = None
