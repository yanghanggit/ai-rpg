from typing import List, Union
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel


ChatRequestMessageListType = List[SystemMessage | HumanMessage | AIMessage]


############################################################################################################
class ChatRequestModel(BaseModel):
    input: str = ""
    chat_history: ChatRequestMessageListType = []

    class Config:
        arbitrary_types_allowed = True


############################################################################################################
class ChatResponseModel(BaseModel):
    output: str = ""

    class Config:
        arbitrary_types_allowed = True


############################################################################################################
