from typing import Dict, List, final

from pydantic import BaseModel, Field

from .blueprint import Blueprint
from .dungeon import Dungeon
from .messages import ChatMessage
from .serialization import EntitySerialization


###############################################################################################################################################
@final
class AgentMemory(BaseModel):
    name: str
    messages: List[ChatMessage]
    context_usage_ratio: float = 0.0  # 最新一次 LLM 调用的上下文占比；未调用时为 0.0


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
            system_rules="",
            knowledge_base={},
            stages=[],
            world_entities=[],
        )
    )
    agent_memories: Dict[str, AgentMemory] = {}


###############################################################################################################################################
