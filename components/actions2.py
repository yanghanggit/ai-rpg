from typing import Dict, Final, NamedTuple, final
from pydantic import BaseModel
from components.registry import register_action_class_2
from tcg_models.v_0_0_1 import Skill


class NullActionModel(BaseModel):
    name: str = "null"


DEFAULT_NULL_ACTION: Final[NullActionModel] = NullActionModel()
############################################################################################################
############################################################################################################


############################################################################################################
# 更新状态
@final
@register_action_class_2
class StatusUpdateAction(NamedTuple):
    base_model: BaseModel


############################################################################################################
# 新的说话action
@final
@register_action_class_2
class SpeakAction2(NamedTuple):
    name: str
    data: Dict[str, str]


############################################################################################################
# 新的说话action
@final
@register_action_class_2
class MindVoiceAction2(NamedTuple):
    name: str
    data: str


############################################################################################################


@final
@register_action_class_2
class SkillAction2(NamedTuple):
    name: str
    skill: Skill


############################################################################################################
