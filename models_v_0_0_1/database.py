from typing import Dict, final
from pydantic import BaseModel


###############################################################################################################################################
@final
class ActorPrototype(BaseModel):
    name: str
    type: str
    profile: str
    appearance: str


###############################################################################################################################################
@final
class StagePrototype(BaseModel):
    name: str
    type: str
    profile: str


###############################################################################################################################################
@final
class DataBase(BaseModel):
    actors: Dict[str, ActorPrototype] = {}
    stages: Dict[str, StagePrototype] = {}
