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
# 世界状态（WorldState）：运行时全状态容器，序列化为 world_state.json
@final
class WorldState(BaseModel):
    entity_counter: int
    entities: List[EntitySerialization] = []
    dungeon: Dungeon = Field(
        default_factory=lambda: Dungeon(name="", rooms=[], profile="")
    )
    blueprint: Blueprint = Field(
        default_factory=lambda: Blueprint(
            name="",
            player_actor="",
            campaign_setting="",
            knowledge_base={},
            stages=[],
            world_entities=[],
            storage_entity="",
        )
    )
    agents_context: Dict[str, AgentContext] = {}


###############################################################################################################################################
