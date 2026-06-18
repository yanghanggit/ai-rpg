"""游戏动作组件。添加到实体后由对应系统处理执行。"""

from typing import Dict, List, Optional, final
from ..entitas.components import Component
from .cards import Card
from .items import ConsumableItem, CostumeItem, GearItem, MaterialItem
from .registry import register_action_component_type, register_component_type


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PlanAction(Component):
    """触发角色在家园场景中生成 AI 行动规划。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class SpeakAction(Component):
    """触发角色向目标角色发送对话消息，广播到整个场景。"""

    name: str
    target_messages: Dict[str, str]  # 目标角色名 → 消息内容


############################################################################################################
@final
@register_action_component_type
@register_component_type
class WhisperAction(Component):
    """触发角色向目标角色发送私密消息，只有双方可见。"""

    name: str
    target_messages: Dict[str, str]  # 目标角色名 → 消息内容


############################################################################################################
@final
@register_action_component_type
@register_component_type
class AnnounceAction(Component):
    """触发角色向当前场景类型的所有场景广播公告。"""

    name: str
    message: str


################################################################################################################
@final
@register_action_component_type
@register_component_type
class QueryAction(Component):
    """触发角色向系统发起查询请求。"""

    name: str
    question: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class TransStageAction(Component):
    """触发角色移动到目标场景。"""

    name: str
    target_stage_name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class UpdateAppearanceAction(Component):
    """触发角色更新外观。穿：从玩家 StorageComponent 取出指定时装挂载 CostumeComponent；脱：移除 CostumeComponent 并将时装归还玩家 StorageComponent。"""

    name: str
    costume_item_name: (
        str  # 穿：指向玩家 StorageComponent 中 CostumeItem 的名称；脱：空字符串
    )
    costume_item: Optional[CostumeItem] = None  # 穿：检索出的时装对象；脱：None


############################################################################################################
@final
@register_action_component_type
@register_component_type
class DrawCardsAction(Component):
    """触发角色在战斗回合中抽取卡牌。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PlayCardsAction(Component):
    """触发角色使用手牌对目标释放技能。"""

    name: str
    card: Card  # 使用的卡牌
    targets: List[str]  # 技能目标角色名列表
    action: str  # 第一人称叙事；空字符串时仲裁 agent 自行演绎


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PassTurnAction(Component):
    """触发角色主动跳过本次出牌机会，消耗 1 点 energy，推进行动顺序。"""

    name: str


############################################################################################################


@final
@register_action_component_type
@register_component_type
class AddStatusEffectsAction(Component):
    """触发对当前场景所有参战角色进行状态效果评估。"""

    name: str
    task_hints: List[
        str
    ]  # 注入提示词的评估背景说明列表，每条 hint 对应一个待生成的状态效果


############################################################################################################
@final
@register_action_component_type
@register_component_type
class RetreatAction(Component):
    """触发角色从战斗中撤退。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class MonsterTurnAction(Component):
    """标记当前轮到指定怪物行动，触发 MonsterPrePlaySystem 进行出牌决策。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class GenerateDungeonAction(Component):
    """触发地下城文本数据完整创建流程（生态→场景→怪物→组装），完成后自动触发图片生成。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class IllustrateDungeonAction(Component):
    """触发地下城封面与 Stage 插图的并发生成。"""

    name: str
    dungeon_name: str  # 地下城全名，用于定位磁盘上的蓝图 JSON


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PostArbitrationAction(Component):
    """仲裁结算后由 stage agent 决定是否追加状态效果或塞入卡牌。"""

    name: str
    current_turn_actor_name: str  # 本次出牌者名称，用于 LLM 上下文


############################################################################################################
@final
@register_action_component_type
@register_component_type
class CraftConsumableAction(Component):
    """触发玩家在工坊用储物箱内的材料合成消耗品，由 LLM（WorkshopComponent agent）推理生成结果。"""

    name: str
    material_names: List[
        str
    ]  # 参与合成的材料名称列表（精确匹配 StorageComponent 中的 MaterialItem）
    material_items: List[MaterialItem] = (
        []
    )  # 预填充的材料对象列表（count = 本次使用量）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class CraftGearItemAction(Component):
    """触发玩家在工坊用储物箱内的材料合成装备，由 LLM（WorkshopComponent agent）推理生成结果。"""

    name: str
    material_names: List[
        str
    ]  # 参与合成的材料名称列表（精确匹配 StorageComponent 中的 MaterialItem）
    material_items: List[MaterialItem] = (
        []
    )  # 预填充的材料对象列表（count = 本次使用量）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class UseConsumableItemAction(Component):
    """触发角色在战斗中使用背包内的消耗品，由 LLM 仲裁效果（HP 变化、状态效果等）。"""

    name: str
    item: ConsumableItem  # 使用的消耗品对象（从 InventoryComponent 检索后填入）
    targets: List[str]  # 技能目标角色名列表（由 target_type 解析后填入）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class UseGearItemAction(Component):
    """触发角色在战斗中使用背包内装备，由系统替换目标已装备 GearItem 并由 LLM 仲裁附加效果。"""

    name: str
    item: GearItem  # 使用的装备对象（从 InventoryComponent 检索后填入）
    targets: List[
        str
    ]  # 装备目标角色名列表（由 target_type 解析后填入；当前期望单目标）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class GenerateDeckAction(Component):
    """触发为角色生成战斗初始牌库，由 DeckGenerationSystem 响应处理。"""

    name: str
    num_cards: int  # 本场战斗为该角色生成的卡牌数（PartyMember=3，Monster=1）
