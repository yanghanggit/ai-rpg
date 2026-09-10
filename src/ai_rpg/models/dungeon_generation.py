"""副本生成流水线的中间数据模型。"""

from typing import List, Literal, final
from pydantic import BaseModel


####################################################################################################################################
@final
class DungeonRoomData(BaseModel):
    """Step 2 中间数据：单个房间的类型、名称、环境描写与角色种类数量。"""

    room_type: Literal["opening", "combat"]  # 房间类型：opening=开场叙事，combat=战斗
    room_name: str = ""
    profile: str = ""
    actor_count: int = 0  # 角色种类数量（opening 房间固定为 0）


####################################################################################################################################
@final
class DungeonActorData(BaseModel):
    """Step 3 中间数据：单个怪物及其归属房间。"""

    room_name: str = (
        ""  # 归属房间全名（「房间.XXXX」，与 DungeonRoomData.room_name 一致）
    )
    actor_name: str = ""
    profile: str = ""
    base_body: str = ""


####################################################################################################################################
@final
class DungeonActorBlueprint(BaseModel):
    """副本怪物实体创建所需的原始字段。供 assemble_dungeon_system 使用。"""

    actor_name: str = ""
    profile: str = ""
    base_body: str = ""


####################################################################################################################################
@final
class DungeonRoomBlueprint(BaseModel):
    """副本单个房间实体创建所需的原始字段（包含配对的怪物蓝图）。供 assemble_dungeon_system 使用。"""

    room_type: Literal["opening", "combat"]  # 房间类型
    room_name: str = ""
    profile: str = ""
    actors: List[DungeonActorBlueprint] = []


####################################################################################################################################
@final
class DungeonBlueprint(BaseModel):
    """副本完整蓝图，承载 Steps 1-3 的全部产出。供 assemble_dungeon_system 使用。"""

    dungeon_name: str = ""
    profile: str = ""
    rooms: List[DungeonRoomBlueprint] = []
