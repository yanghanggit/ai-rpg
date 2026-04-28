"""游戏动作组件定义模块

定义游戏中所有角色可执行的动作类型，包括：
- 行动规划与场景切换
- 通信交互（对话、耳语、公告、查询）
- 战斗操作（抽牌、出牌）

动作组件采用 ECS 响应式架构，添加到实体后由对应系统处理执行。
"""

from typing import Dict, List, Optional, final
from ..entitas.components import Component
from .combat import Card
from .registry import register_action_component_type, register_component_type


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
class InspectSelfAction(Component):
    """自我审视动作组件

    触发角色查阅自身背包（InventoryComponent）与战斗属性（CharacterStatsComponent），
    由 InspectSelfActionSystem 将格式化后的信息注入 LLM context。

    Attributes:
        name: 发起查阅的角色名称
    """

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class EquipItemAction(Component):
    """装备物品动作组件

    触发角色将背包中指定物品装备到对应槽位，并由 EquipItemActionSystem
    更新 EquipmentComponent 并重新合成 AppearanceComponent。

    每个字段对应一个装备槽：None 表示不更换该槽；"" 表示脱掉该槽；
    非空字符串表示装备该物品。
    建议在装备前先用 InspectSelfAction 查阅背包中物品的精确全名。

    Attributes:
        name: 发起装备操作的角色名称
        weapon: 目标武器物品全名（None 不更换；"" 脱掉）
        armor: 目标套装物品全名（None 不更换；"" 脱掉）
        accessory: 目标饰品物品全名（None 不更换；"" 脱掉）
    """

    name: str
    weapon: Optional[str] = None
    armor: Optional[str] = None
    accessory: Optional[str] = None


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
    """

    name: str


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
        action: 出牌时的情景化第一人称叙事（与具体战场绑定）；
                ally 路径默认为空字符串，enemy 路径由 LLM 在出牌决策时生成；
                为空时仲裁 agent 将自行根据卡牌描述与战场情境演绎；
                空卡占位时传入空字符串
    """

    name: str
    card: Card
    targets: List[str]
    action: str


############################################################################################################


@final
@register_action_component_type
@register_component_type
class AddStatusEffectsAction(Component):
    """添加状态效果动作组件

    触发 AddStatusEffectsActionSystem 对当前场景所有参战角色进行状态效果评估。

    Attributes:
        name: 发起评估的实体名称
        task_hint: 任务说明，注入到提示词中以补充当前回合的评估背景与意图
    """

    name: str
    task_hint: str


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


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PostArbitrationAction(Component):
    """仲裁后场景效果动作组件

    由 ArbitrationActionSystem 在每次真实仲裁结算成功后添加到 stage entity，
    触发 PostArbitrationActionSystem 以 stage agent（地牢主视角）决定
    是否向场内参战角色追加状态效果或塞入卡牌。
    动作组件由 ActionCleanupSystem 自动清除，无需手动移除。

    Attributes:
        name: stage entity 名称
        current_turn_actor_name: 本次仲裁的出牌者名称（用于向 LLM 传递上下文）
    """

    name: str
    current_turn_actor_name: str
