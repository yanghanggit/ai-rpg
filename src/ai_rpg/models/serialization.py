from typing import Any, Dict, List, final
from pydantic import BaseModel, ConfigDict


###############################################################################################################################################
@final
class ComponentSerialization(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    data: Dict[str, Any]


###############################################################################################################################################
@final
class EntitySerialization(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    components: List[ComponentSerialization]


###############################################################################################################################################
