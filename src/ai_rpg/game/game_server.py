"""游戏服务器模块

本模块提供游戏服务器的核心管理功能，主要负责：
- 管理所有玩家房间（Room）的生命周期
- 存储和管理后台异步任务状态
- 提供房间的创建、查询、删除等操作接口

GameServer 作为单例存在，通过依赖注入在整个应用中共享。
"""

from typing import Dict, Optional
from .room import Room
from ..models import TaskRecord, TaskStatus
import uuid
from datetime import datetime


###############################################################################################################################################
class GameServer:
    """游戏服务器类

    管理所有玩家房间和后台任务的中心服务器实例。
    每个玩家通过 user_name 唯一标识，对应一个独立的 Room。
    """

    def __init__(
        self,
    ) -> None:
        """初始化游戏服务器

        创建空的房间字典和后台任务存储。
        """
        self._rooms: Dict[str, Room] = {}
        self._background_task_store: Dict[str, TaskRecord] = {}

    ###############################################################################################################################################
    def has_room(self, user_name: str) -> bool:
        """检查指定玩家的房间是否存在

        Args:
            user_name: 玩家用户名

        Returns:
            bool: 房间存在返回 True，否则返回 False
        """
        return user_name in self._rooms

    ###############################################################################################################################################
    def get_room(self, user_name: str) -> Optional[Room]:
        """获取指定玩家的房间

        Args:
            user_name: 玩家用户名

        Returns:
            Optional[Room]: 房间实例，不存在则返回 None
        """
        return self._rooms.get(user_name, None)

    ###############################################################################################################################################
    def create_room(self, user_name: str) -> Room:
        """为指定玩家创建新房间

        Args:
            user_name: 玩家用户名

        Returns:
            Room: 新创建的房间实例

        Raises:
            AssertionError: 如果房间已存在
        """
        if self.has_room(user_name):
            assert False, f"room {user_name} already exists"
        room = Room(user_name)
        self._rooms[user_name] = room
        return room

    ###############################################################################################################################################
    def remove_room(self, room: Room) -> None:
        """移除指定的房间

        Args:
            room: 要移除的房间实例

        Raises:
            AssertionError: 如果房间不存在
        """
        user_name = room._username
        assert user_name in self._rooms
        self._rooms.pop(user_name, None)

    ###############################################################################################################################################
    def create_task(self) -> TaskRecord:
        """创建并添加一个新的后台任务记录

        Returns:
            TaskRecord: 新创建的任务记录对象
        """

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
        """获取指定的后台任务记录

        Args:
            task_id: 任务唯一标识符

        Returns:
            Optional[TaskRecord]: 任务记录对象，不存在则返回 None
        """
        return self._background_task_store.get(task_id, None)

    ###############################################################################################################################################
