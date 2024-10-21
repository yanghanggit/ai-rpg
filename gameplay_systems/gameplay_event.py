from typing import final
from my_data.model_def import BaseAgentEvent


# 临时测试重构用！
class AgentEvent(BaseAgentEvent):
    pass


@final
class UpdateAppearanceEvent(AgentEvent):
    pass
