from typing import Dict, final
from ..entitas.components import Component
from .dungeon import Skill
from .registry import register_action_class, register_component_class


############################################################################################################
# 新的说话action
@final
@register_component_class
@register_action_class
class SpeakAction(Component):
    name: str
    data: Dict[str, str]


############################################################################################################
# 新的耳语action
@final
@register_component_class
@register_action_class
class WhisperAction(Component):
    name: str
    data: Dict[str, str]


############################################################################################################
# 新的宣布action
@final
@register_component_class
@register_action_class
class AnnounceAction(Component):
    name: str
    data: str


############################################################################################################
# 新的说话action
@final
@register_component_class
@register_action_class
class MindVoiceAction(Component):
    name: str
    data: str


############################################################################################################
@final
@register_component_class
@register_action_class
class DrawCardsAction(Component):
    name: str


############################################################################################################
@final
@register_component_class
@register_action_class
class PlayCardsAction(Component):
    name: str
    skill: Skill
    target: str
    # dialogue: str
    # reason: str


############################################################################################################
@final
@register_component_class
@register_action_class
class ArbitrationAction(Component):
    name: str
    calculation: str
    performance: str


############################################################################################################
