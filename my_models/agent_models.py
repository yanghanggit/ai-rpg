from typing import List, List
from pydantic import BaseModel
from enum import StrEnum


class AgentMessageType(StrEnum):
    STSTEM = "SystemMessage"
    HUMAN = "HumanMessage"
    AI = "AIMessage"


class AgentMessageModel(BaseModel):
    message_type: AgentMessageType
    content: str


class AgentChatHistoryDumpModel(BaseModel):
    name: str
    url: str
    chat_history: List[AgentMessageModel]
