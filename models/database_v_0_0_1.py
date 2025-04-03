from typing import Final, Dict, final
from pydantic import BaseModel


# 注意，不允许动！
SCHEMA_VERSION: Final[str] = "0.0.1"


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
