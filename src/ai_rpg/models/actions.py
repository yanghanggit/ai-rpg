from typing import Dict, final
from ..entitas.components import Component
from .dungeon import Skill
from .registry import register_action_class, register_component_class


############################################################################################################
@final
@register_component_class
@register_action_class
class PlanAction(Component):
    name: str


############################################################################################################
@final
@register_component_class
@register_action_class
class SpeakAction(Component):
    name: str
    data: Dict[str, str]


############################################################################################################
@final
@register_component_class
@register_action_class
class WhisperAction(Component):
    name: str
    data: Dict[str, str]


############################################################################################################
@final
@register_component_class
@register_action_class
class AnnounceAction(Component):
    name: str
    data: str


############################################################################################################
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


############################################################################################################
@final
@register_component_class
@register_action_class
class ArbitrationAction(Component):
    name: str
    calculation: str
    performance: str


############################################################################################################
