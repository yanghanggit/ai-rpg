from typing import Dict, final

from pydantic import BaseModel, Field

from ..entitas import ContextData
from .agent_memory import AgentMemory
from .blueprint import Blueprint
from .dungeon import Dungeon


###############################################################################################################################################
# 世界状态（WorldState）：运行时全状态容器，序列化为 world_state.json
@final
class WorldState(BaseModel):
    entity_counter: int
    entities: ContextData = {}
    dungeon: Dungeon = Field(
        default_factory=lambda: Dungeon(name="", rooms=[], profile="")
    )
    blueprint: Blueprint = Field(
        default_factory=lambda: Blueprint(
            name="",
            player_actor="",
            campaign_setting="",
            system_rules="",
            knowledge_base={},
            stages=[],
            world_entities=[],
        )
    )
    agent_memories: Dict[str, AgentMemory] = {}


###############################################################################################################################################
