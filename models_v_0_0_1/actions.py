from typing import Dict, NamedTuple, final, List
from .dungeon import Skill, StatusEffect
from .registry import register_component_class, register_action_class


############################################################################################################
# 新的说话action
@final
@register_component_class
@register_action_class
class SpeakAction(NamedTuple):
    name: str
    data: Dict[str, str]


############################################################################################################
# 新的耳语action
@final
@register_component_class
@register_action_class
class WhisperAction(NamedTuple):
    name: str
    data: Dict[str, str]


############################################################################################################
# 新的宣布action
@final
@register_component_class
@register_action_class
class AnnounceAction(NamedTuple):
    name: str
    data: str


############################################################################################################
# 新的说话action
@final
@register_component_class
@register_action_class
class MindVoiceAction(NamedTuple):
    name: str
    data: str


############################################################################################################
@final
@register_component_class
@register_action_class
class TurnAction(NamedTuple):
    name: str
    rounds: int
    round_turns: List[str]
    skill: str

    @property
    def turn(self) -> int:
        return self.round_turns.index(self.name)


############################################################################################################
@final
@register_component_class
@register_action_class
class PlayCardsAction(NamedTuple):
    name: str
    targets: List[str]
    skill: Skill
    dialogue: str
    reason: str


############################################################################################################
@final
@register_component_class
@register_action_class
class DirectorAction(NamedTuple):
    name: str
    calculation: str
    performance: str


############################################################################################################
@final
@register_component_class
@register_action_class
class FeedbackAction(NamedTuple):
    name: str
    calculation: str
    performance: str
    description: str
    update_hp: int
    update_max_hp: int
    effects: List[StatusEffect]


############################################################################################################
