from typing import List, Dict, final
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .snapshot import EntitySnapshot
from .database import DataBase
from .objects import Actor, Stage, WorldSystem
from .dungeon import Dungeon
from .registry import register_base_model_class


###############################################################################################################################################
# 生成世界的根文件，就是世界的起点
@final
@register_base_model_class
class Boot(BaseModel):
    name: str
    campaign_setting: str = ""
    stages: List[Stage] = []
    world_systems: List[WorldSystem] = []
    data_base: DataBase = DataBase()

    @property
    def actors(self) -> List[Actor]:
        return [actor for stage in self.stages for actor in stage.actors]


###############################################################################################################################################
@final
@register_base_model_class
class AgentShortTermMemory(BaseModel):
    name: str
    chat_history: List[SystemMessage | HumanMessage | AIMessage] = []


###############################################################################################################################################
# 生成世界的运行时文件，记录世界的状态
@final
@register_base_model_class
class World(BaseModel):
    runtime_index: int = 1000
    entities_snapshot: List[EntitySnapshot] = []
    agents_short_term_memory: Dict[str, AgentShortTermMemory] = {}
    dungeon: Dungeon = Dungeon(name="")
    boot: Boot = Boot(name="")

    @property
    def version(self) -> str:
        return "0.0.1"

    @property
    def data_base(self) -> DataBase:
        return self.boot.data_base

    def next_runtime_index(self) -> int:
        self.runtime_index += 1
        return self.runtime_index


###############################################################################################################################################
