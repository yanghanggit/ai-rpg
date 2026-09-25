"""游戏服务器模块。

职责：进程内玩家房间注册表（``user_name -> PlayerRoom``）。

并发模型
--------
* ``GameServer`` 只负责房间的**注册 / 注销**，用内部 ``asyncio.Lock`` 保证注册表
  变更（create / remove）的原子性；``has_room`` / ``get_room`` 是单事件循环下的
  原子只读操作。
* 房间**内部状态**的一致性由 ``PlayerRoom`` 自己的锁负责，统一通过
  ``async with game_server.acquire(user_name) as room:`` 进入。
* 移除房间时 ``remove_room`` 会等待该房间进行中的事务结束再关闭，避免后台任务
  与登出并发写坏状态。

注意：注册表是进程内内存态，因此本服务不支持多 worker / 多进程部署。
空闲房间由 ``reap_expired`` 按 TTL 回收。
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Optional, List

from .player_room import PlayerRoom


###############################################################################################################################################
class RoomNotFoundError(Exception):
    """请求的房间不存在。"""

    def __init__(self, user_name: str) -> None:
        super().__init__(f"room not found: {user_name}")
        self.user_name: str = user_name


###############################################################################################################################################
class RoomAlreadyExistsError(Exception):
    """创建房间时同名房间已存在。"""

    def __init__(self, user_name: str) -> None:
        super().__init__(f"room already exists: {user_name}")
        self.user_name: str = user_name


###############################################################################################################################################
class GameServer:
    """游戏服务器类（进程内房间注册表）。"""

    def __init__(
        self,
    ) -> None:
        self._rooms: Dict[str, PlayerRoom] = {}
        self._lock: asyncio.Lock = asyncio.Lock()  # 保护 _rooms 注册表变更

    ###############################################################################################################################################
    def has_room(self, user_name: str) -> bool:
        """检查指定玩家的房间是否存在"""
        return user_name in self._rooms

    ###############################################################################################################################################
    def get_room(self, user_name: str) -> Optional[PlayerRoom]:
        """获取指定玩家的房间（同时刷新其活跃时间）。"""
        room = self._rooms.get(user_name, None)
        if room is not None:
            room.touch()
        return room

    ###############################################################################################################################################
    async def create_room(self, user_name: str) -> PlayerRoom:
        """为指定玩家创建新房间；房间已存在时抛 ``RoomAlreadyExistsError``。"""
        async with self._lock:

            # 检查房间是否已存在
            if user_name in self._rooms:
                raise RoomAlreadyExistsError(user_name)

            # 创建新房间实例并注册到房间表
            room = PlayerRoom(user_name)
            self._rooms[user_name] = room
            return room

    ###############################################################################################################################################
    async def remove_room(self, user_name: str) -> Optional[PlayerRoom]:
        """移除并关闭指定玩家的房间。

        先从注册表摘除（后续 ``get_room`` 立即不可见），再等待该房间进行中的事务
        结束后关闭它，确保不会在任务运行时清空状态。房间不存在时返回 ``None``。
        """

        async with self._lock:
            # 从注册表中摘除房间
            room = self._rooms.pop(user_name, None)

        # 如果房间存在，等待其进行中的事务结束后关闭房间
        if room is not None:
            await room.close()

        return room

    ###############################################################################################################################################
    async def reap_expired(
        self, ttl: float, *, now: Optional[float] = None
    ) -> List[str]:
        """回收空闲超过 ``ttl`` 秒且不在忙的房间，返回被回收的玩家名。"""
        current = time.monotonic() if now is None else now
        deadline = current - ttl
        reaped: List[str] = []

        # 遍历所有房间，尝试回收空闲房间
        for name, room in list(self._rooms.items()):

            # 尝试回收空闲房间，如果房间仍然忙或未达到回收条件则跳过
            if not await room.evict_if_idle(deadline):
                continue

            # 从注册表中移除已回收的房间
            async with self._lock:
                if self._rooms.get(name) is room:
                    self._rooms.pop(name, None)

            # 将已回收的房间加入回收列表
            reaped.append(name)

        # 返回所有已回收的房间列表
        return reaped

    ###############################################################################################################################################
    @asynccontextmanager
    async def acquire(self, user_name: str) -> AsyncGenerator[PlayerRoom, None]:
        """获取房间并在其事务锁内执行；房间不存在时抛 ``RoomNotFoundError``。

        这是进入房间临界区的**统一入口**，后台任务应优先使用它，避免重复
        ``get_room`` + 手动取锁。
        """
        room = self.get_room(user_name)
        if room is None:
            # 房间不存在，抛出异常
            raise RoomNotFoundError(user_name)

        # 获取到房间实例，准备进入事务锁临界区
        async with room.transaction():
            yield room

    ###############################################################################################################################################
