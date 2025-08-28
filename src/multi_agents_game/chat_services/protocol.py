from typing import List, TypeAlias

from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict

ChatRequestMessageListType: TypeAlias = List[SystemMessage | HumanMessage | AIMessage]


############################################################################################################
class ChatRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    message: HumanMessage
    chat_history: ChatRequestMessageListType = []


############################################################################################################
class ChatResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: List[BaseMessage] = []


############################################################################################################
