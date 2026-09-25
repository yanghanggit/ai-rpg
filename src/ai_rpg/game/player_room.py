"""玩家房间模块。

并发模型
--------
* **并发单元是 ``PlayerRoom``**：同一玩家的所有游戏状态变更必须串行执行。
* **锁由 ``PlayerRoom`` 自己持有**，外部只能通过 ``async with room.transaction():``
  进入临界区，禁止直接访问 ``_lock``。
* **只读访问**通过 ``room.game`` / ``room.player_session`` 属性读取；这两个属性
  返回稳定的对象引用，不额外加锁，以免查询接口被长耗时 pipeline 阻塞。
* 房间被 ``close()`` 后，后续 ``transaction()`` 会抛出 ``RoomClosedError``，
  避免在已移除的房间上继续变更状态。
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Final, Optional

from ..models import PlayerSession
from .dbg_game import DBGGame


###############################################################################################################################################
class RoomClosedError(RuntimeError):
    """在已关闭（已登出 / 已移除）的房间上进入事务时抛出。"""

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
        """房间所属玩家名。"""
        return self._username

    @property
    def game(self) -> Optional[DBGGame]:
        """当前游戏实例（只读快照，可能为 None）。"""
        return self._dbg_game

    @property
    def player_session(self) -> Optional[PlayerSession]:
        """当前玩家会话实例（只读快照，可能为 None）。"""
        return self._player_session

    @property
    def is_closed(self) -> bool:
        """房间是否已关闭。"""
        return self._closed

    ###############################################################################################################################################
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator["PlayerRoom", None]:
        """进入该玩家房间的临界区。

        同一房间同一时刻只允许一个事务；房间已关闭时拒绝进入。所有对房间状态的
        变更（以及需要一致快照的读取）都应在此上下文内完成。
        """
        async with self._lock:
            if self._closed:
                raise RoomClosedError(self._username)
            yield self

    ###############################################################################################################################################
    def bind(self, *, game: DBGGame, player_session: PlayerSession) -> None:
        """绑定房间的游戏与会话实例。

        必须在 ``async with room.transaction():`` 内调用；外部不得直接写
        ``_dbg_game`` / ``_player_session``。
        """
        assert not self._closed, "不能在已关闭的房间上绑定游戏"
        self._dbg_game = game
        self._player_session = player_session

    ###############################################################################################################################################
    async def close(self) -> None:
        """关闭房间：等待进行中的事务结束后清空状态并标记为已关闭。"""
        async with self._lock:
            self._closed = True
            self._dbg_game = None
            self._player_session = None

    ###############################################################################################################################################
