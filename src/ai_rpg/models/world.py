from typing import Dict, List, final
from .messages import ContextMessage
from pydantic import BaseModel
from .dungeon import Dungeon
from .entities import Actor, Stage, WorldSystem
from .items import AnyItem
from .serialization import EntitySerialization


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

    @property
    def actors(self) -> List[Actor]:
        return [actor for stage in self.stages for actor in stage.actors]


###############################################################################################################################################
@final
class AgentContext(BaseModel):
    name: str
    context: List[ContextMessage]


###############################################################################################################################################
# 生成世界的运行时文件，记录世界的状态
@final
class World(BaseModel):
    entity_counter: int
    home_planning_turn_index: int
    entities_serialization: List[EntitySerialization]
    agents_context: Dict[str, AgentContext]
    dungeon: Dungeon
    blueprint: Blueprint


###############################################################################################################################################
