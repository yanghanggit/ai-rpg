from overrides import final
from pydantic import BaseModel
from typing import Any


# 根类 连接 player 与 entity的 2个大部分。
class BaseEvent(BaseModel):
    message: str


# 广播用的实现，这里只是一个例子，实际上可能会有很多不同的实现
class AgentEvent(BaseEvent):

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(*args, **kwargs)
        data["class_name"] = self.__class__.__name__
        return data


# 以下是一些具体的事件-------------------------------------------------------------


# 这个事件是用来更新外观的
@final
class UpdateAppearanceEvent(AgentEvent):
    pass


# 这个事件是用来通知进入场景的
@final
class PreStageExitEvent(AgentEvent):
    pass


# 广播内容事件
@final
class BroadcastEvent(AgentEvent):
    announcer_name: str
    stage_name: str
    content: str


# 说话事件
@final
class SpeakEvent(AgentEvent):
    speaker_name: str
    target_name: str
    content: str


# 私语事件
@final
class WhisperEvent(AgentEvent):
    whisperer_name: str
    target_name: str
    content: str
