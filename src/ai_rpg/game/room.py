from typing import Final, Optional
from .tcg_game import TCGGame
from .player_session import PlayerSession


class Room:
    """
    游戏房间类

    为单个玩家提供独立的游戏空间，管理玩家的游戏实例和会话状态。
    每个房间可以容纳不同类型的游戏实例（TCG或SDG），同一时间只能运行一个游戏。

    主要功能：
    - 管理玩家的游戏实例生命周期
    - 维护玩家会话状态
    - 支持多种游戏类型切换

    Attributes:
        _username: 房间所属玩家的用户名（只读）
        _tcg_game: 交易卡牌游戏实例（可选）
        _sdg_game: 故事驱动游戏实例（可选）
        _player_session: 玩家会话实例（可选）

    Note:
        - 每个房间绑定到唯一的用户名
        - 同一时间只能有一个游戏实例处于活动状态
        - 玩家会话用于跟踪游戏过程中的所有事件和消息
    """

    def __init__(self, username: str) -> None:
        self._username: Final[str] = username
        self._tcg_game: Optional[TCGGame] = None  # TCGGame 游戏实例
        self._player_session: Optional[PlayerSession] = None
