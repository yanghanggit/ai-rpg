from enum import IntEnum, unique
from typing import Dict, List, final
from pydantic import BaseModel


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
