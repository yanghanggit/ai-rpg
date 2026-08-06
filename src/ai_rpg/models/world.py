from typing import Dict, List, final
from .messages import ContextMessage
from pydantic import BaseModel, Field
from .dungeon import Dungeon
from .serialization import EntitySerialization
from .blueprint import Blueprint


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
    entities: List[EntitySerialization] = []
    dungeon: Dungeon = Field(
        default_factory=lambda: Dungeon(name="", rooms=[], premise="")
    )
    blueprint: Blueprint = Field(
        default_factory=lambda: Blueprint(
            name="",
            player_actor="",
            campaign_setting="",
            knowledge_base={},
            stages=[],
            world_systems=[],
            storage_entity="",
        )
    )
    agents_context: Dict[str, AgentContext] = {}


###############################################################################################################################################
