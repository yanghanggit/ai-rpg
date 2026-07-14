from datetime import datetime, timezone
from typing import Annotated, List, Literal, Optional, Union, final
from pydantic import BaseModel, Field
from .combat import Combat
from .entities import Stage
from .image import GeneratedImage


###############################################################################################################################################
class DungeonRoom(BaseModel):
    """地下城房间基类（关卡包装）"""

    type: Literal["base"] = "base"  # 判别字段，子类收窄为对应 Literal 值
    stage: Stage  # 必须，对应关卡场景
    image: GeneratedImage = GeneratedImage()  # 当前房间的文生图数据，默认为空


###############################################################################################################################################
@final
class CombatRoom(DungeonRoom):
    """战斗房间（含战斗数据）"""

    type: Literal["combat"] = "combat"  # type: ignore[assignment]
    combat: Combat = Combat(name="")  # 当前房间的战斗数据，默认为空战斗（state=NONE）


###############################################################################################################################################
# 判别联合类型：可基于 type 字段进行精确的反序列化
AnyDungeonRoom = Annotated[
    Union[DungeonRoom, CombatRoom],
    Field(discriminator="type"),
]


###############################################################################################################################################
@final
class Dungeon(BaseModel):
    """地下城模型"""

    name: str
    rooms: List[AnyDungeonRoom]
    ecology: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )  # 创建时间戳（UTC）
    current_room_index: int = -1  # 当前所在房间索引，初始为 -1，表示尚未进入任何房间
    setup_entities: bool = (
        False  # 是否已经根据模型创建了实体（敌人和场景），默认 False，创建后置 True
    )
    image: GeneratedImage = GeneratedImage()  # 地下城封面文生图数据，默认为空

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
