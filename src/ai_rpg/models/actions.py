"""游戏动作组件定义模块"""

from typing import Dict, List, final
from ..entitas.components import Component
from .dungeon import Card, StatusEffect
from .registry import register_action_component_type, register_component_type
from .entities import Skill


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
    """抽牌动作组件

    触发角色在战斗回合中抽取卡牌，由 DrawCardsActionSystem 处理生成具体卡牌。

    Attributes:
        name: 执行抽牌的角色名称
        skill: 用于生成卡牌的技能
        targets: 技能目标列表
        status_effects: 附加状态效果列表
    """

    name: str
    skill: Skill
    targets: List[str]
    status_effects: List[StatusEffect]


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PlayCardsAction(Component):
    name: str
    card: Card
    targets: List[str]


############################################################################################################
