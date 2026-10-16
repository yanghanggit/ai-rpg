from datetime import datetime, timezone
from typing import Dict, List, Optional, final

from pydantic import BaseModel, Field

from .assets_meta import AssetKey
from .dungeon_room import AnyDungeonRoom


###############################################################################################################################################
@final
class Dungeon(BaseModel):
    """副本模型"""

    name: str
    rooms: List[AnyDungeonRoom]
    profile: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )  # 创建时间戳（UTC）
    current_room_index: int = -1  # 当前所在房间索引，初始为 -1，表示尚未进入任何房间
    assets: Dict[AssetKey, str] = Field(
        default_factory=dict
    )  # 副本封面等资源：AssetKey -> meta 路径（.assets/image/<file>.meta）
    archive_summary: str = ""  # 副本结束归档时由副本导演生成的总结正文，初始为空

    ########################################################################################################################
    @property
    def current_room(self) -> Optional[AnyDungeonRoom]:
        return self.get_room(self.current_room_index)

    ########################################################################################################################
    def get_room(self, index: int) -> Optional[AnyDungeonRoom]:
        """根据索引获取房间，如果索引无效返回 None。"""
        if index >= 0 and index < len(self.rooms):
            return self.rooms[index]
        return None
