from typing import List, Dict, final
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .snapshot import EntitySnapshot
from .objects import Actor, Stage, WorldSystem
from .dungeon import Dungeon


###############################################################################################################################################
# 生成世界的根文件，就是世界的起点
@final
class Boot(BaseModel):
    name: str
    campaign_setting: str = ""
    stages: List[Stage] = []
    world_systems: List[WorldSystem] = []

    @property
    def actors(self) -> List[Actor]:
        return [actor for stage in self.stages for actor in stage.actors]


###############################################################################################################################################
@final
class AgentShortTermMemory(BaseModel):
    name: str
    chat_history: List[SystemMessage | HumanMessage | AIMessage] = []


###############################################################################################################################################
# 生成世界的运行时文件，记录世界的状态
@final
class World(BaseModel):
    runtime_index: int = 1000
    entities_snapshot: List[EntitySnapshot] = []
    agents_short_term_memory: Dict[str, AgentShortTermMemory] = {}
    dungeon: Dungeon = Dungeon(name="")
    boot: Boot = Boot(name="")

    def next_runtime_index(self) -> int:
        self.runtime_index += 1
        return self.runtime_index


###############################################################################################################################################
