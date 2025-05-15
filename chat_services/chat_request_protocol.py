from typing import List, Union
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel


############################################################################################################
class ChatRequestModel(BaseModel):
    agent_name: str = ""
    user_name: str = ""
    input: str = ""
    chat_history: List[Union[SystemMessage, HumanMessage, AIMessage]] = []

    class Config:
        arbitrary_types_allowed = True


############################################################################################################
class ChatResponseModel(BaseModel):
    agent_name: str = ""
    user_name: str = ""
    output: str = ""

    class Config:
        arbitrary_types_allowed = True


############################################################################################################
