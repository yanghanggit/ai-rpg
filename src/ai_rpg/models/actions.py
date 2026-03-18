"""游戏动作组件定义模块

定义游戏中所有角色可执行的动作类型，包括：
- 行动规划与场景切换
- 通信交互（对话、耳语、公告、查询）
- 战斗操作（抽牌、出牌）

动作组件采用 ECS 响应式架构，添加到实体后由对应系统处理执行。
"""

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
    """行动规划动作组件

    触发角色在家园场景中生成AI行动规划。

    Attributes:
        name: 执行规划的角色名称
    """

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class SpeakAction(Component):
    """对话动作组件

    触发角色向目标角色发送对话消息，消息会广播到整个场景。

    Attributes:
        name: 发送消息的角色名称
        target_messages: 目标角色名称到消息内容的映射
    """

    name: str
    target_messages: Dict[str, str]


############################################################################################################
@final
@register_action_component_type
@register_component_type
class WhisperAction(Component):
    """耳语动作组件

    触发角色向目标角色发送私密消息，只有双方能收到。

    Attributes:
        name: 发送耳语的角色名称
        target_messages: 目标角色名称到消息内容的映射
    """

    name: str
    target_messages: Dict[str, str]


############################################################################################################
@final
@register_action_component_type
@register_component_type
class AnnounceAction(Component):
    """公告动作组件

    触发角色向当前场景类型的所有场景广播公告消息。

    Attributes:
        name: 发送公告的角色名称
        message: 公告消息内容
    """

    name: str
    message: str


################################################################################################################
@final
@register_action_component_type
@register_component_type
class QueryAction(Component):
    """查询动作组件

    触发角色向系统发起查询请求。

    Attributes:
        name: 发起查询的角色名称
        question: 查询问题内容
    """

    name: str
    question: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class TransStageAction(Component):
    """场景转换动作组件

    触发角色从当前场景移动到目标场景。

    Attributes:
        name: 执行移动的角色名称
        target_stage_name: 目标场景名称
    """

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
    """出牌动作组件

    触发角色在战斗回合中使用手牌对目标释放技能。

    Attributes:
        name: 出牌的角色名称
        card: 使用的卡牌
        targets: 技能目标列表
    """

    name: str
    card: Card
    targets: List[str]


############################################################################################################


@final
@register_action_component_type
@register_component_type
class RetreatAction(Component):
    """
    战斗中角色撤退动作组件
    """

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class GenerateDungeonAction(Component):
    """地下城生成动作组件。

    在家园状态下主动添加到玩家实体，触发 GenerateDungeonActionSystem 执行
    地下城文本数据的完整创建流程（Steps 1-4：生态→场景→怪物→组装）。
    流程成功后自动添加 IllustrateDungeonAction 以触发图片生成系统。
    动作组件由 ActionCleanupSystem 自动清除，无需手动移除。

    Attributes:
        name: 发起创建请求的实体名称
    """

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class IllustrateDungeonAction(Component):
    """地下城图片生成动作组件。

    由 GenerateDungeonActionSystem 在文本数据生成成功后自动添加到玩家实体，
    触发 IllustrateDungeonActionSystem 执行地下城封面与 Stage 插图的并发生成。
    动作组件由 ActionCleanupSystem 自动清除，无需手动移除。

    Attributes:
        name: 发起创建请求的实体名称
        dungeon_name: 地下城全名（用于定位磁盘上的 DungeonBlueprint JSON）
    """

    name: str
    dungeon_name: str
