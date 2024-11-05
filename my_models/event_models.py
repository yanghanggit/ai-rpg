from overrides import final
from pydantic import BaseModel


class BaseAgentEvent(BaseModel):
    message_content: str


# 临时测试重构用！
class AgentEvent(BaseAgentEvent):
    pass


@final
class UpdateAppearanceEvent(AgentEvent):
    pass
