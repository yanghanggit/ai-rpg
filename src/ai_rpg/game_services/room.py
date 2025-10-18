from typing import Final, Optional
from ..game.tcg_game import TCGGame, SDGame
from ..game.player_session import PlayerSession


class Room:

    def __init__(self, username: str) -> None:
        self._username: Final[str] = username
        self._tcg_game: Optional[TCGGame] = None  # TCGGame 游戏实例
        self._sd_game: Optional[SDGame] = None  # SDGame 实例
        self._player_session: Optional[PlayerSession] = None
