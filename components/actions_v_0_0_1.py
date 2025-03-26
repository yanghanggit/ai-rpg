from typing import Dict, NamedTuple, final, List
from components.registry import register_action_class_2
from models.v_0_0_1 import Skill, Effect


############################################################################################################
# 新的说话action
@final
@register_action_class_2
class SpeakAction(NamedTuple):
    name: str
    data: Dict[str, str]


############################################################################################################
# 新的耳语action
@final
@register_action_class_2
class WhisperAction(NamedTuple):
    name: str
    data: Dict[str, str]


############################################################################################################
# 新的宣布action
@final
@register_action_class_2
class AnnounceAction(NamedTuple):
    name: str
    data: str


############################################################################################################
# 新的说话action
@final
@register_action_class_2
class MindVoiceAction(NamedTuple):
    name: str
    data: str


############################################################################################################
@final
@register_action_class_2
class TurnAction(NamedTuple):
    name: str
    rounds: int
    round_turns: List[str]

    @property
    def turn(self) -> int:
        return self.round_turns.index(self.name)


############################################################################################################
@final
@register_action_class_2
class SelectAction(NamedTuple):
    name: str
    targets: List[str]
    skill: Skill
    interaction: str
    reason: str


############################################################################################################
@final
@register_action_class_2
class StageDirectorAction(NamedTuple):
    name: str
    calculation: str
    performance: str


############################################################################################################
@final
@register_action_class_2
class FeedbackAction(NamedTuple):
    name: str
    calculation: str
    performance: str
    description: str
    hp: float
    max_hp: float
    effects: List[Effect]


############################################################################################################
