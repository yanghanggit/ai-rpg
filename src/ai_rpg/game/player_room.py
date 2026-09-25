"""玩家房间模块。

并发约定：写经 ``transaction()`` 串行；读不加锁，直接取 ``game`` / ``player_session``。
"""

import asyncio
import time
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
        self._last_active_at: float = time.monotonic()

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
        """是否有进行中的事务（供定时器/回收器等需非阻塞判断的场景使用）。"""
        return self._lock.locked()

    def touch(self) -> None:
        """刷新房间活跃时间。"""
        self._last_active_at = time.monotonic()

    ###############################################################################################################################################
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator["PlayerRoom", None]:
        """进入房间临界区，仅用于写变更。"""
        self.touch()
        async with self._lock:
            if self._closed:
                raise RoomClosedError(self._username)
            yield self

    ###############################################################################################################################################
    def bind(self, *, game: DBGGame, player_session: PlayerSession) -> None:
        """绑定游戏与会话实例，应在 ``transaction()`` 内调用。"""
        if self._closed:
            raise RoomClosedError(self._username)
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
    async def evict_if_idle(self, deadline: float) -> bool:
        """若房间不忙且活跃时间早于 deadline，则退出游戏并关闭；返回是否已关闭。"""
        if self._lock.locked():
            return False

        async with self._lock:

            # 检查房间是否已关闭或仍然活跃
            if self._closed or self._last_active_at > deadline:
                return False

            # 退出游戏并关闭房间
            if self._dbg_game is not None:
                self._dbg_game.exit()

            # 标记房间为已关闭并清理游戏与会话实例
            self._closed = True
            self._dbg_game = None
            self._player_session = None
            return True

    ###############################################################################################################################################
