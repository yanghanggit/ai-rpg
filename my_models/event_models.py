from overrides import final
from pydantic import BaseModel


# 根类 连接 player 与 entity的 2个大部分。
class BaseEvent(BaseModel):
    message_content: str


# 广播用的实现，这里只是一个例子，实际上可能会有很多不同的实现
class AgentEvent(BaseEvent):
    pass


@final
class UpdateAppearanceEvent(AgentEvent):
    pass
