import asyncio
from typing import Final, Optional
from .dbg_game import DBGGame
from ..models import PlayerSession


class PlayerRoom:
    """
    游戏房间类
    """

    def __init__(self, username: str) -> None:
        self._username: Final[str] = username
        self._dbg_game: Optional[DBGGame] = None  # DBGGame 游戏实例
        self._player_session: Optional[PlayerSession] = None
        self._lock: asyncio.Lock = asyncio.Lock()  # 每玩家锁，防止并发状态竞争
