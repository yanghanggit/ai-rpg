import asyncio
from typing import Final, Optional
from .dbg_game import DBGGame
from ..models import PlayerSession


class PlayerRoom:
    """
    游戏房间类

    为单个玩家提供独立的游戏空间，管理玩家的游戏实例和会话状态。

    Attributes:
        _username: 房间所属玩家的用户名（只读）
        _dbg_game: DBG 游戏实例（可选）
        _player_session: 玩家会话实例（可选）
        _lock: 每玩家异步互斥锁，防止同一玩家的并发请求产生状态竞争
    """

    def __init__(self, username: str) -> None:
        self._username: Final[str] = username
        self._dbg_game: Optional[DBGGame] = None  # DBGGame 游戏实例
        self._player_session: Optional[PlayerSession] = None
        self._lock: asyncio.Lock = asyncio.Lock()  # 每玩家锁，防止并发状态竞争
