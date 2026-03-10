import asyncio
from typing import Final, Optional
from .tcg_game import TCGGame
from .player_session import PlayerSession


class Room:
    """
    游戏房间类

    为单个玩家提供独立的游戏空间，管理玩家的游戏实例和会话状态。

    Attributes:
        _username: 房间所属玩家的用户名（只读）
        _tcg_game: 交易卡牌游戏实例（可选）
        _player_session: 玩家会话实例（可选）
        _lock: 每玩家异步互斥锁，防止同一玩家的并发请求产生状态竞争
    """

    def __init__(self, username: str) -> None:
        self._username: Final[str] = username
        self._tcg_game: Optional[TCGGame] = None  # TCGGame 游戏实例
        self._player_session: Optional[PlayerSession] = None
        self._lock: asyncio.Lock = asyncio.Lock()  # 每玩家锁，防止并发状态竞争

    #################################################################################
    @property
    def lock(self) -> asyncio.Lock:
        """获取房间锁对象"""
        return self._lock
