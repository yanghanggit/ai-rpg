from typing import List
from langchain.schema import AIMessage, HumanMessage, SystemMessage, BaseMessage
from pydantic import BaseModel


ChatRequestMessageListType = List[SystemMessage | HumanMessage | AIMessage]


############################################################################################################
class ChatRequest(BaseModel):
    message: HumanMessage
    chat_history: ChatRequestMessageListType = []

    class Config:
        arbitrary_types_allowed = True


############################################################################################################
class ChatResponse(BaseModel):
    messages: List[BaseMessage] = []

    class Config:
        arbitrary_types_allowed = True


############################################################################################################
