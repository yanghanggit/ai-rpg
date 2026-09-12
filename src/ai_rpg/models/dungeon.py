from datetime import datetime, timezone
from typing import Annotated, List, Literal, Optional, Union, final
from pydantic import BaseModel, Field
from .combat import Combat
from .entities import Stage
from .image import GeneratedImage


###############################################################################################################################################
class DungeonRoom(BaseModel):
    """副本房间基类（抽象关卡包装）：不直接实例化，具体房间见 OpeningRoom / CombatRoom。"""

    type: str  # 判别字段，子类收窄为各自的 Literal 值
    stage: Stage  # 必须，对应关卡场景
    image: GeneratedImage = GeneratedImage()  # 当前房间的文生图数据，默认为空


###############################################################################################################################################
@final
class CombatRoom(DungeonRoom):
    """战斗房间（含战斗数据）"""

    type: Literal["combat"] = "combat"
    combat: Combat = Combat(name="")  # 当前房间的战斗数据，默认为空战斗（state=NONE）


###############################################################################################################################################
@final
class OpeningRoom(DungeonRoom):
    """开场房间（非战斗叙事场景，用于副本开场铺垫）"""

    type: Literal["opening"] = "opening"
    initialized: bool = (
        False  # 是否已完成开场初始化（叙事 + 牌库初始化），用于幂等状态守护；卡池生成由外部显式触发
    )


###############################################################################################################################################
# 判别联合类型：基于 type 字段进行精确的反序列化。
# 只含具体房间：DungeonRoom 是抽象基类，"base" 房间不存在，故不进入联合。
AnyDungeonRoom = Annotated[
    Union[OpeningRoom, CombatRoom],
    Field(discriminator="type"),
]


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
    setup_entities: bool = (
        False  # 是否已经根据模型创建了实体（敌人和场景），默认 False，创建后置 True
    )
    image: GeneratedImage = GeneratedImage()  # 副本封面文生图数据，默认为空

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
