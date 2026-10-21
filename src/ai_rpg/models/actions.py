"""游戏动作组件。添加到实体后由对应系统处理执行。"""

from enum import StrEnum, unique
from typing import Dict, List, Optional, final

from ..entitas.components import Component
from .card import Card
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
class CompactContextAction(Component):
    """触发对指定 agent 的记忆进行手动上下文压缩。

    动作挂载在被压缩实体自身，name 即该实体名；由
    CompactContextActionSystem 响应 ADDED 事件执行压缩。
    """

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
class TransStageAction(Component):
    """触发角色移动到目标场景。"""

    name: str
    target_stage_name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class WearCostumeAction(Component):
    """触发角色穿上指定时装：从玩家 StorageComponent 取出指定时装挂载 WornCostumeComponent（若已穿戴其他时装，先自动脱下归还）。"""

    name: str
    costume_item_name: str  # 指向玩家 StorageComponent 中 CostumeItem 的名称
    costume_item: CostumeItem  # 检索出的时装对象


############################################################################################################
@final
@register_action_component_type
@register_component_type
class RemoveCostumeAction(Component):
    """触发角色脱下当前穿戴的时装：移除 WornCostumeComponent 并将时装归还玩家 StorageComponent。"""

    name: str


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
class RetreatAction(Component):
    """触发角色从战斗中撤退。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class MonsterTurnAction(Component):
    """标记当前轮到指定怪物行动，触发 MonsterCombatDecisionSystem 进行出牌决策。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class GenerateDungeonAction(Component):
    """副本生成流程入口。

    由 home_actions.activate_generate_dungeon() 在家园状态下添加到副本生成系统实体，
    驱动 dungeon_generate_pipeline 在本次 process() 内顺序跑完整个副本创建流程。
    """

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class CraftConsumableItemAction(Component):
    """触发玩家在消耗品工坊用储物箱内的材料合成消耗品，由 LLM（ConsumableWorkshopComponent agent）推理生成结果。"""

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
    """触发玩家在装备工坊用储物箱内的材料合成装备，由 LLM（GearWorkshopComponent agent）推理生成结果。"""

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
class CraftCostumeItemAction(Component):
    """触发玩家在时装工坊用储物箱内的材料制作时装，由 LLM（CostumeWorkshopComponent agent）推理生成结果。"""

    name: str
    material_names: List[
        str
    ]  # 参与制作的材料名称列表（精确匹配 StorageComponent 中的 MaterialItem）
    material_items: List[MaterialItem] = (
        []
    )  # 预填充的材料对象列表（count = 本次使用量）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class UseConsumableItemAction(Component):
    """触发当前行动者使用队伍背包内的消耗品：扣减库存并把其内置卡牌物化进手牌。"""

    name: str
    item: ConsumableItem  # 使用的消耗品对象（从队伍背包 InventoryComponent 检索后填入）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class EquipGearItemAction(Component):
    """触发当前行动者（我方）将团队背包内的装备转化为手牌。"""

    name: str
    item: GearItem  # 使用的装备对象（从 InventoryComponent 检索后填入）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class GenerateSpoilsAction(Component):
    """触发为角色生成候选奖励（SpoilsComponent），当前生成候选卡牌。"""

    name: str


############################################################################################################
@final
@unique
class SpoilRewardKind(StrEnum):
    """Spoils 奖励类型；用于区分 PickSpoilsAction 的领取子操作。"""

    CARD = "card"  # 卡牌（当前唯一实现；未来可扩展 ITEM / ARTIFACT）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PickSpoilsAction(Component):
    """触发角色从 SpoilsComponent 领取一项奖励（umbrella）。

    当前仅实现卡牌子操作（reward_kind=CARD），由 activate_pick_spoils_card
    检索后填入 card；未来可扩展 item / artifact 等子操作。
    """

    name: str
    reward_kind: SpoilRewardKind = SpoilRewardKind.CARD  # 领取的奖励类型
    card: Optional[Card] = None  # reward_kind == CARD 时有效


############################################################################################################
@final
@register_action_component_type
@register_component_type
class FillDrawPileAction(Component):
    """触发从 DeckComponent 洗牌填充 DrawPileComponent，由 FillDrawPileSystem 响应处理。"""

    name: str
