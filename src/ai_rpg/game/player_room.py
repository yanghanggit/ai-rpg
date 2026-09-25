"""玩家房间模块。

并发约定：写经 ``transaction()`` 串行；读不加锁，直接取 ``game`` / ``player_session``。
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Final, Optional

from ..models import PlayerSession
from .dbg_game import DBGGame


###############################################################################################################################################
class RoomClosedError(RuntimeError):
    """在已关闭的房间上进入事务时抛出。"""

    def __init__(self, username: str) -> None:
        super().__init__(f"room closed: {username}")
        self.username: str = username


###############################################################################################################################################
class PlayerRoom:
    """游戏房间类。"""

    def __init__(self, username: str) -> None:
        self._username: Final[str] = username
        self._dbg_game: Optional[DBGGame] = None  # DBGGame 游戏实例
        self._player_session: Optional[PlayerSession] = None
        self._lock: asyncio.Lock = asyncio.Lock()  # 每玩家锁，防止并发状态竞争
        self._closed: bool = False

    ###############################################################################################################################################
    @property
    def username(self) -> str:
        return self._username

    @property
    def game(self) -> Optional[DBGGame]:
        return self._dbg_game

    @property
    def player_session(self) -> Optional[PlayerSession]:
        return self._player_session

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def is_busy(self) -> bool:
        """是否有房间事务正在执行。"""
        return self._lock.locked()

    ###############################################################################################################################################
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator["PlayerRoom", None]:
        """进入房间临界区，仅用于写变更。"""
        async with self._lock:
            if self._closed:
                raise RoomClosedError(self._username)
            yield self

    ###############################################################################################################################################
    def bind(self, *, game: DBGGame, player_session: PlayerSession) -> None:
        """绑定游戏与会话实例，应在 ``transaction()`` 内调用。"""
        assert not self._closed, "不能在已关闭的房间上绑定游戏"
        self._dbg_game = game
        self._player_session = player_session

    ###############################################################################################################################################
    async def close(self) -> None:
        """等待进行中的事务结束后清空状态并关闭房间。"""
        async with self._lock:
            self._closed = True
            self._dbg_game = None
            self._player_session = None

    ###############################################################################################################################################
