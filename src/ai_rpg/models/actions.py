"""游戏动作组件。添加到实体后由对应系统处理执行。"""

from typing import Dict, List, final
from ..entitas.components import Component
from .card import Card
from .items import ConsumableItem, CostumeItem, GearItem, MaterialItem
from .registry import register_action_component_type, register_component_type
from .status_effect import AffixTrigger


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
class AddStatusEffectsAction(Component):
    """触发对当前场景所有参战角色进行状态效果评估。"""

    name: str
    affix_triggers: List[
        AffixTrigger
    ]  # affixes 触发信号列表，每条对应一个待生成的状态效果，与 StatusEffect 严格 1:1


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
# ── 副本生成流程（Step 0-4）内部衔接 Action ──────────────────────────────────────────────────────────
# 触发链（全部在同一次 dungeon_generate_pipeline.process() 内顺序完成）：
#   GenerateDungeonAction
#     → GenerateDungeonDirectiveSystem (Step 0) → GenerateDungeonDirectiveAction
#     → GenerateDungeonProfileSystem    (Step 1) → GenerateDungeonStagesAction
#     → GenerateDungeonStagesSystem    (Step 2) → GenerateDungeonActorsAction
#     → GenerateDungeonActorsSystem    (Step 3) → AssembleDungeonAction
#     → AssembleDungeonSystem          (Step 4) → IllustrateDungeonAction
#     → IllustrateDungeonActionSystem  (Step 5)
############################################################################################################
@final
@register_action_component_type
@register_component_type
class GenerateDungeonAction(Component):
    """副本生成流程入口。

    由 home_actions.activate_generate_dungeon() 在家园状态下添加到副本生成系统实体，
    触发 GenerateDungeonDirectiveSystem（Step 0）执行世界导演指令推理。
    """

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class GenerateDungeonDirectiveAction(Component):
    """Step 0→1 衔接：由 GenerateDungeonDirectiveSystem 添加，携带世界导演创作指令。

    触发 GenerateDungeonProfileSystem（Step 1），其读取 directive 注入首轮 prompt。
    """

    name: str
    directive: str = ""


############################################################################################################
@final
@register_action_component_type
@register_component_type
class GenerateDungeonStagesAction(Component):
    """Step 1→2 衔接：由 GenerateDungeonProfileSystem 添加，携带副本设定产物。

    触发 GenerateDungeonStagesSystem（Step 2），其直接读取本组件的字段。
    """

    name: str
    dungeon_name: str
    dungeon_profile: str = ""
    # TODO: 语义待重构——目标为「副本房间总数（含入口）」，届时移除下游 `1 + ...` 的 +1 entry 写法
    dungeon_room_count: int = 2  # 当前临时语义：战斗房间数量（不含入口房间）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class GenerateDungeonActorsAction(Component):
    """ """

    name: str
    dungeon_name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class AssembleDungeonAction(Component):
    """ """

    name: str
    dungeon_name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class IllustrateDungeonAction(Component):
    """Step 4→5 衔接：由 AssembleDungeonSystem 添加，触发副本封面与 Stage 插图的并发生成。"""

    name: str
    dungeon_name: str  # 副本全名，用于定位磁盘上的 .dungeons/{dungeon_name}.json


############################################################################################################
@final
@register_action_component_type
@register_component_type
class CraftConsumableItemAction(Component):
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
class CraftCostumeItemAction(Component):
    """触发玩家在工坊用储物箱内的材料制作时装，由 LLM（WorkshopComponent agent）推理生成结果。"""

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
    targets: List[str]  # 装备目标角色名列表（固定为单一友方目标）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class GenerateDeckAction(Component):
    """触发为角色生成战斗初始牌库，由 DeckGenerationSystem 响应处理。"""

    name: str
