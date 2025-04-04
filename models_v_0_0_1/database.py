from typing import Dict, final
from pydantic import BaseModel
from .registry import register_base_model_class


###############################################################################################################################################
@final
@register_base_model_class
class ActorPrototype(BaseModel):
    name: str
    type: str
    profile: str
    appearance: str


###############################################################################################################################################
@final
@register_base_model_class
class StagePrototype(BaseModel):
    name: str
    type: str
    profile: str


###############################################################################################################################################
@final
@register_base_model_class
class DataBase(BaseModel):
    actors: Dict[str, ActorPrototype] = {}
    stages: Dict[str, StagePrototype] = {}
