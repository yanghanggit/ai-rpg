from pydantic import BaseModel
from enum import StrEnum
from my_data.model_def import AgentEvent


class PlayerClientMessageTag(StrEnum):
    SYSTEM = "SYSTEM"
    ACTOR = "ACTOR"
    STAGE = "STAGE"


class PlayerClientMessage(BaseModel):
    tag: PlayerClientMessageTag
    sender: str
    event: AgentEvent