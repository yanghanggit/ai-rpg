from typing import Optional, final
from pydantic import BaseModel
from .agent_event import AnyAgentEvent


@final
class SessionMessage(BaseModel):
    agent_event: Optional[AnyAgentEvent] = None
    sequence_id: int = 0
