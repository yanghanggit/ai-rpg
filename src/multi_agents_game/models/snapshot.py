from typing import List, Dict, Any, final
from pydantic import BaseModel
from .registry import register_base_model_class


###############################################################################################################################################
@final
@register_base_model_class
class ComponentSnapshot(BaseModel):
    name: str
    data: Dict[str, Any]


###############################################################################################################################################
@final
@register_base_model_class
class EntitySnapshot(BaseModel):
    name: str
    components: List[ComponentSnapshot]


###############################################################################################################################################
