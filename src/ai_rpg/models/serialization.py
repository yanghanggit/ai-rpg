from typing import Any, Dict, List, final
from pydantic import BaseModel


###############################################################################################################################################
@final
class ComponentSerialization(BaseModel):
    name: str
    data: Dict[str, Any]


###############################################################################################################################################
@final
class EntitySerialization(BaseModel):
    name: str
    components: List[ComponentSerialization]


###############################################################################################################################################
