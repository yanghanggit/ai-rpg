"""游戏服务器模块"""

from typing import Dict, Optional
from .player_room import PlayerRoom
from ..models import TaskRecord, TaskStatus
import uuid
from datetime import datetime


###############################################################################################################################################
class GameServer:
    """游戏服务器类"""

    def __init__(
        self,
    ) -> None:
        self._rooms: Dict[str, PlayerRoom] = {}
        self._background_task_store: Dict[str, TaskRecord] = {}

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
    def create_task(self) -> TaskRecord:
        """创建并添加一个新的后台任务记录"""

        task_id = str(uuid.uuid4())
        task_record = TaskRecord(
            task_id=task_id,
            status=TaskStatus.RUNNING,
            start_time=datetime.now().isoformat(),
        )

        # 不可能出现重复ID！
        assert task_id not in self._background_task_store
        self._background_task_store[task_id] = task_record

        return task_record

    ###############################################################################################################################################
    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """获取指定的后台任务记录"""
        return self._background_task_store.get(task_id, None)

    ###############################################################################################################################################
