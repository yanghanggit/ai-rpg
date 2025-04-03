from typing import Dict, NamedTuple, final, List
from .registry import register_action_class
from .dungeon import Skill, StatusEffect


############################################################################################################
# 新的说话action
@final
@register_action_class
class SpeakAction(NamedTuple):
    name: str
    data: Dict[str, str]


############################################################################################################
# 新的耳语action
@final
@register_action_class
class WhisperAction(NamedTuple):
    name: str
    data: Dict[str, str]


############################################################################################################
# 新的宣布action
@final
@register_action_class
class AnnounceAction(NamedTuple):
    name: str
    data: str


############################################################################################################
# 新的说话action
@final
@register_action_class
class MindVoiceAction(NamedTuple):
    name: str
    data: str


############################################################################################################
@final
@register_action_class
class TurnAction(NamedTuple):
    name: str
    rounds: int
    round_turns: List[str]

    @property
    def turn(self) -> int:
        return self.round_turns.index(self.name)


############################################################################################################
@final
@register_action_class
class PlayCardAction(NamedTuple):
    name: str
    targets: List[str]
    skill: Skill
    interaction: str
    reason: str


############################################################################################################
@final
@register_action_class
class StageDirectorAction(NamedTuple):
    name: str
    calculation: str
    performance: str


############################################################################################################
@final
@register_action_class
class FeedbackAction(NamedTuple):
    name: str
    calculation: str
    performance: str
    description: str
    hp: float
    max_hp: float
    effects: List[StatusEffect]


############################################################################################################
