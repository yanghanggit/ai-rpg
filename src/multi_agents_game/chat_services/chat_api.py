from typing import List

from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict

ChatRequestMessageListType = List[SystemMessage | HumanMessage | AIMessage]


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
