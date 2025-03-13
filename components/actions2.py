from typing import Final, NamedTuple, final
from pydantic import BaseModel
from components.registry import register_action_class_2


class NullActionModel(BaseModel):
    name: str = "null-action"


DEFAULT_NULL_ACTION: Final[NullActionModel] = NullActionModel()


class ActionComponent2(NamedTuple):
    data: BaseModel = DEFAULT_NULL_ACTION


############################################################################################################
# 更新状态
@final
@register_action_class_2
class StatusUpdateAction(ActionComponent2):
    pass
