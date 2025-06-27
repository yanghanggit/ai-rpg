from typing import Dict, final
from pydantic import BaseModel
from .registry import register_base_model_class


###############################################################################################################################################
@final
@register_base_model_class
class ActorCharacterSheet(BaseModel):
    name: str
    type: str
    profile: str
    appearance: str


###############################################################################################################################################
@final
@register_base_model_class
class StageCharacterSheet(BaseModel):
    name: str
    type: str
    profile: str


###############################################################################################################################################
@final
@register_base_model_class
class DataBase(BaseModel):
    actor_character_sheets: Dict[str, ActorCharacterSheet] = {}
    stage_character_sheets: Dict[str, StageCharacterSheet] = {}
