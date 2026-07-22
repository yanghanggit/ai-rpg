from typing import List, final
from pydantic import BaseModel
from .entities import Stage, WorldSystem
from .items import AnyItem
from .artifacts import Artifact


###############################################################################################################################################
# 生成世界的根文件，就是世界的起点
@final
class Blueprint(BaseModel):
    name: str
    player_actor: str
    campaign_setting: str
    stages: List[Stage]
    world_systems: List[WorldSystem]
    storage_entity: str  # 全局储物箱实体名
    storage: List[AnyItem] = []  # 蓝图初始储物箱道具库
    inventory: List[AnyItem] = []  # 蓝图初始玩家背包道具库
    artifacts: List[Artifact] = []  # 蓝图初始世界神器/古物库


###############################################################################################################################################
