from enum import IntEnum, unique
from typing import Dict, List, final
from pydantic import BaseModel
from models.event_models import BaseEvent


@final
@unique
class ClientMessageHead(IntEnum):
    NONE = 0
    AGENT_EVENT = 1
    MAPPING = 2


class ClientMessage(BaseModel):
    head: int = ClientMessageHead.NONE
    body: str = ""


class AgentEventMessage(BaseModel):
    agent_event: BaseEvent = BaseEvent(message="")


class MappingMessage(BaseModel):
    data: Dict[str, List[str]] = {}
