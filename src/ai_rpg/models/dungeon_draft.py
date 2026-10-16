"""副本生成流水线的中间数据模型。"""

from typing import Final, List, Literal, final

from pydantic import BaseModel

####################################################################################################################################
# 副本结构（单一事实来源）：当前为便于测试与调试采用最小规模。
# 这些数值会写进「世界.副本生成系统」的系统提示词；改后须重新刷蓝图（python -m scripts.setup_demo）。
OPENING_ROOM_COUNT: Final[int] = 1  # 开场房间数：无战斗，纯门口氛围铺垫
COMBAT_ROOM_COUNT: Final[int] = 1  # 战斗房间数
MONSTERS_PER_COMBAT_ROOM: Final[int] = 1  # 每个战斗房间的怪物数
DUNGEON_ROOM_COUNT: Final[int] = OPENING_ROOM_COUNT + COMBAT_ROOM_COUNT  # 副本房间总数


####################################################################################################################################
@final
class DungeonRoomDraft(BaseModel):
    """单个房间的类型、名称、环境描写与角色种类数量。"""

    room_type: Literal["opening", "combat"]  # 房间类型：opening=开场叙事，combat=战斗
    room_name: str = ""
    profile: str = ""
    actor_count: int = 0  # 角色种类数量（opening 房间固定为 0）


####################################################################################################################################
@final
class DungeonActorDraft(BaseModel):
    """单个怪物及其归属房间。"""

    room_name: str = (
        ""  # 归属房间全名（「房间.XXXX」，与 DungeonRoomDraft.room_name 一致）
    )
    actor_name: str = ""
    profile: str = ""
    base_body: str = ""


####################################################################################################################################
@final
class DungeonDraft(BaseModel):
    """副本生成的中间过程数据。

    挂在 DBGGame 上（与 _world 平级），不落盘；组装完成后由尾部系统清空，
    流程中途断掉即视为放弃。
    """

    directive: str = ""  # 世界导演的副本创作指令
    dungeon_name: str = ""
    profile: str = ""
    room_count: int = DUNGEON_ROOM_COUNT  # 副本房间总数（含 1 个开场房间）
    rooms: List[DungeonRoomDraft] = []
    actors: List[DungeonActorDraft] = []
