from typing import Dict, List, final
from .messages import ContextMessage
from pydantic import BaseModel
from .dungeon import Dungeon
from .serialization import EntitySerialization
from .blue_print import Blueprint


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
    entities_serialization: List[EntitySerialization]
    agents_context: Dict[str, AgentContext]
    dungeon: Dungeon
    blueprint: Blueprint


###############################################################################################################################################
