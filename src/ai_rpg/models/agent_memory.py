from typing import List, final

from pydantic import BaseModel

from .messages import ChatMessage


###############################################################################################################################################
@final
class AgentMemory(BaseModel):
    name: str
    messages: List[ChatMessage]
    context_usage_ratio: float = 0.0  # 最新一次 LLM 调用的上下文占比；未调用时为 0.0


###############################################################################################################################################
