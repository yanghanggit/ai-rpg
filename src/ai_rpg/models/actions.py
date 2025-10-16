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
    target_messages: Dict[str, str]


############################################################################################################
@final
@register_component_class
@register_action_class
class WhisperAction(Component):
    name: str
    target_messages: Dict[str, str]


############################################################################################################
@final
@register_component_class
@register_action_class
class AnnounceAction(Component):
    name: str
    message: str


############################################################################################################
@final
@register_component_class
@register_action_class
class MindVoiceAction(Component):
    name: str
    message: str


################################################################################################################
@final
@register_component_class
@register_action_class
class QueryAction(Component):
    name: str
    question: str


############################################################################################################
@final
@register_component_class
@register_action_class
class TransStageAction(Component):
    name: str
    target_stage_name: str


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


@final
@register_component_class
@register_action_class
class DiscussionAction(Component):
    name: str
    message: str


############################################################################################################
@final
@register_component_class
@register_action_class
class NightPlanAction(Component):
    name: str


############################################################################################################


# @final
# @register_component_class
# @register_action_class
# class WolfKillAction(Component):
#     name: str
#     werewolf_name: str
#     message: str


############################################################################################################


@final
@register_component_class
@register_action_class
class SeerCheckAction(Component):
    name: str
    seer_name: str


############################################################################################################


@final
@register_component_class
@register_action_class
class WitchPoisonAction(Component):
    name: str
    witch_name: str


############################################################################################################
@final
@register_component_class
@register_action_class
class WitchCureAction(Component):
    name: str
    witch_name: str


############################################################################################################
@final
@register_component_class
@register_action_class
class VoteAction(Component):
    name: str
    target_name: str


############################################################################################################
