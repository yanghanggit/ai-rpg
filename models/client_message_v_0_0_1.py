from enum import IntEnum, unique
from typing import Dict, Final, List, final
from pydantic import BaseModel

# 注意，不允许动！
SCHEMA_VERSION: Final[str] = "0.0.1"


@final
@unique
class ClientMessageHead(IntEnum):
    NONE = 0
    AGENT_EVENT = 1
    MAPPING = 2


class ClientMessage(BaseModel):
    head: int = ClientMessageHead.NONE
    body: str = ""


class MappingMessage(BaseModel):
    data: Dict[str, List[str]] = {}
