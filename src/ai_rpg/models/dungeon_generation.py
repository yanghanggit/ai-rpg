"""副本生成流水线的中间数据模型。"""

from typing import Literal, final
from pydantic import BaseModel


####################################################################################################################################
@final
class DungeonRoomData(BaseModel):
    """Step 2 中间数据：单个房间的类型、名称、标识、环境描写与角色种类数量。"""

    room_type: Literal["entry", "combat"]  # 房间类型：entry=叙事入口，combat=战斗
    room_name: str = ""
    profile_name: str = ""
    profile: str = ""
    actor_count: int = 0  # 角色种类数量（entry 房间固定为 0）
