from pydantic import BaseModel
from enum import StrEnum
from my_data.model_def import BaseAgentEvent


class PlayerClientMessageTag(StrEnum):
    SYSTEM = "SYSTEM"
    ACTOR = "ACTOR"
    STAGE = "STAGE"
    KICKOFF = "KICKOFF"
    TIP = "TIP"


class PlayerClientMessage(BaseModel):
    tag: PlayerClientMessageTag
    sender: str
    agent_event: BaseAgentEvent  # 要根部的类，其实只需要它的序列化能力，其余的不要，所以不要出现具体类型的调用！
