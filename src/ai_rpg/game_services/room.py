from typing import Final, Optional
from ..game.tcg_game import TCGGame
from ..game.sdg_game import SDGGame
from ..game.player_session import PlayerSession


class Room:

    def __init__(self, username: str) -> None:
        self._username: Final[str] = username
        self._tcg_game: Optional[TCGGame] = None  # TCGGame 游戏实例
        self._sdg_game: Optional[SDGGame] = None  # SDGame 实例
        self._player_session: Optional[PlayerSession] = None
