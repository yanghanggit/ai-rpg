"""游戏服务器模块"""

from typing import Dict, Optional
from .player_room import PlayerRoom


###############################################################################################################################################
class GameServer:
    """游戏服务器类"""

    def __init__(
        self,
    ) -> None:
        self._rooms: Dict[str, PlayerRoom] = {}

    ###############################################################################################################################################
    def has_room(self, user_name: str) -> bool:
        """检查指定玩家的房间是否存在"""
        return user_name in self._rooms

    ###############################################################################################################################################
    def get_room(self, user_name: str) -> Optional[PlayerRoom]:
        """获取指定玩家的房间"""
        return self._rooms.get(user_name, None)

    ###############################################################################################################################################
    def create_room(self, user_name: str) -> PlayerRoom:
        """为指定玩家创建新房间"""
        if self.has_room(user_name):
            assert False, f"room {user_name} already exists"
        room = PlayerRoom(user_name)
        self._rooms[user_name] = room
        return room

    ###############################################################################################################################################
    def remove_room(self, room: PlayerRoom) -> None:
        """移除指定的房间"""
        user_name = room._username
        assert user_name in self._rooms
        self._rooms.pop(user_name, None)

    ###############################################################################################################################################
