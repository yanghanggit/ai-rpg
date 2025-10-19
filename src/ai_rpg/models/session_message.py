from enum import IntEnum, unique
from typing import Dict, final, Any
from pydantic import BaseModel


@final
@unique
class MessageType(IntEnum):
    NONE = 0
    AGENT_EVENT = 1
    GAME = 2


@final
class SessionMessage(BaseModel):
    message_type: int = MessageType.NONE
    data: Dict[str, Any] = {}
    sequence_id: int = 0
