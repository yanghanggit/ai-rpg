from typing import Dict, List, final
from ..entitas.components import Component
from .dungeon import Card
from .registry import register_action_component_type, register_component_type


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PlanAction(Component):
    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class SpeakAction(Component):
    name: str
    target_messages: Dict[str, str]


############################################################################################################
@final
@register_action_component_type
@register_component_type
class WhisperAction(Component):
    name: str
    target_messages: Dict[str, str]


############################################################################################################
@final
@register_action_component_type
@register_component_type
class AnnounceAction(Component):
    name: str
    message: str


################################################################################################################
@final
@register_action_component_type
@register_component_type
class QueryAction(Component):
    name: str
    question: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class TransStageAction(Component):
    name: str
    target_stage_name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class DrawCardsAction(Component):
    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PlayCardsAction(Component):
    name: str
    card: Card
    targets: List[str]


############################################################################################################
@final
@register_action_component_type
@register_component_type
class ArbitrationAction(Component):
    name: str
    calculation: str
    performance: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class DiscussionAction(Component):
    name: str
    message: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class SeerCheckAction(Component):
    name: str
    seer_name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class WitchPoisonAction(Component):
    name: str
    witch_name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class WitchCureAction(Component):
    name: str
    witch_name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class VoteAction(Component):
    name: str
    target_name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class HunterShootAction(Component):
    name: str
    hunter_name: str


############################################################################################################
