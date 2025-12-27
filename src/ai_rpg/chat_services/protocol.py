from typing import List
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict

# ContextMessageType: TypeAlias = List[SystemMessage | HumanMessage | AIMessage]


############################################################################################################
class ChatRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    message: HumanMessage
    context: List[SystemMessage | HumanMessage | AIMessage] = []


############################################################################################################
class ChatResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: List[BaseMessage] = []


############################################################################################################
