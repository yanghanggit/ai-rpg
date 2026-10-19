"""副本生成流水线的中间数据模型。"""

from typing import Final, List, Literal, final

from pydantic import BaseModel

####################################################################################################################################
# 副本结构的「默认值」——不是不变量。
#
# 未来由 LLM 按自身的创作原则与判断决定房间组合，代码只负责给出默认值与合法边界：
# - 开场房间默认且通常恒为 1（无战斗，纯门口氛围铺垫）；
# - 战斗房间数与每个战斗房间的怪物数可能变化。
#
# 这些默认值只用于运行时构造任务提示词与工具 schema，不写进 demo 的系统提示词，
# 因此调整无需重刷蓝图（python -m scripts.setup_demo）。
DEFAULT_OPENING_ROOM_COUNT: Final[int] = 1  # 默认开场房间数：无战斗，纯门口氛围铺垫
DEFAULT_COMBAT_ROOM_COUNT: Final[int] = 1  # 默认战斗房间数
DEFAULT_MONSTERS_PER_COMBAT_ROOM: Final[int] = 1  # 默认每个战斗房间的怪物数
DEFAULT_DUNGEON_ROOM_COUNT: Final[int] = (
    DEFAULT_OPENING_ROOM_COUNT + DEFAULT_COMBAT_ROOM_COUNT
)  # 默认副本房间总数


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
    room_count: int = (
        DEFAULT_DUNGEON_ROOM_COUNT  # 副本房间总数（未规划结构时取默认值，包含开场房间）
    )
    rooms: List[DungeonRoomDraft] = []
    actors: List[DungeonActorDraft] = []
