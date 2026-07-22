"""ECS 组件定义。添加到实体后由对应系统读取处理。"""

from typing import List, final
from ..entitas.components import Component, MutableComponent
from .card import Card
from .status_effect import StatusEffect
from .items import AnyItem, CostumeItem, GearItem
from .stats import CharacterStats
from .registry import register_component_type


############################################################################################################
@final
@register_component_type
class IdentityComponent(Component):
    """为实体提供可读名称、创建顺序与全局唯一 ID。"""

    name: str
    creation_order: int  # 序列化时保证顺序一致性
    entity_id: str  # UUID 格式


############################################################################################################
@final
@register_component_type
class WorldComponent(Component):
    """标记实体为世界系统类型。"""

    name: str


############################################################################################################
@final
@register_component_type
class StageComponent(Component):
    """标记实体为场景类型。"""

    name: str
    character_sheet_name: str  # 场景配置表名称


############################################################################################################
@final
@register_component_type
class ActorComponent(Component):
    """标记实体为角色类型，记录当前所在场景。"""

    name: str
    character_sheet_name: str  # 角色配置表名称
    current_stage: str  # 当前所在场景名称


############################################################################################################
@final
@register_component_type
class StageDescriptionComponent(Component):
    """场景环境叙述，由 AI 根据当前状态动态生成，为行动规划与战斗初始化等系统提供上下文。"""

    name: str
    narrative: str  # 叙述性描述文本


############################################################################################################
@final
@register_component_type
class PlayerComponent(Component):
    """标记角色由玩家控制（全局唯一）。"""

    player_name: str


############################################################################################################
@final
@register_component_type
class DestroyComponent(Component):
    """标记实体在下一帧销毁。"""

    name: str


############################################################################################################
@final
@register_component_type
class AppearanceComponent(Component):
    """存储角色外观描述。`appearance` 由 LLM 基于 `base_body` 与装备合成。"""

    name: str
    base_body: str  # 基础身体形态描述（不含装备）
    appearance: str  # 最终外观描述（含装备）


############################################################################################################
@final
@register_component_type
class HomeComponent(Component):
    """标记场景为家园类型。"""

    name: str


############################################################################################################
@final
@register_component_type
class DungeonComponent(Component):
    """标记场景为地下城类型。"""

    name: str


############################################################################################################
@final
@register_component_type
class NPCComponent(Component):
    """标记角色为 NPC（非玩家控制的友方角色），属于友方阵营。"""

    name: str


############################################################################################################
@final
@register_component_type
class PartyMemberComponent(Component):
    """标记角色为当前地下城远征队活跃成员（NPCComponent 的子集，留守盟友不持有此组件）。"""

    name: str


############################################################################################################
@final
@register_component_type
class PartyRosterComponent(Component):
    """挂载在玩家实体，记录本次远征预选同伴名单；为空时玩家独自冒险。"""

    name: str
    members: List[str]  # 其他远征队员名称（不含玩家自身）


############################################################################################################
@final
@register_component_type
class MonsterComponent(Component):
    """标记角色为怪物（敌方阵营战斗单位）。"""

    name: str


############################################################################################################
@final
@register_component_type
class HandComponent(MutableComponent):
    """存储角色当前手牌与所在回合数。"""

    name: str
    cards: List[Card]
    # round: int  # 当前回合数


############################################################################################################
@final
@register_component_type
class RoundStatsComponent(MutableComponent):
    """本回合动态战斗属性；每回合开始由 CharacterStats 初始化，回合结束清除。"""

    name: str
    energy: int  # 本回合有效行动次数（可被状态效果修改）


############################################################################################################
@final
@register_component_type
class DeathComponent(Component):
    """标记角色已死亡，战斗系统排除此角色。"""

    name: str


############################################################################################################
@final
@register_component_type
class CharacterStatsComponent(MutableComponent):
    """存储角色战斗属性（HP、攻击力、防御力等）。"""

    name: str
    stats: CharacterStats


############################################################################################################


@final
@register_component_type
class StatusEffectsComponent(MutableComponent):
    """存储角色当前状态效果列表。"""

    name: str
    status_effects: List[StatusEffect]


############################################################################################################
@final
@register_component_type
class PlayerActionAuditComponent(Component):
    """标记世界系统实体具有玩家行动审计功能。"""

    name: str


############################################################################################################
@final
@register_component_type
class DungeonGenerationComponent(Component):
    """标记世界系统实体具有地下城图片生成职责。"""

    name: str


############################################################################################################
@final
@register_component_type
class WorkshopComponent(Component):
    """标记世界系统实体具有制造工坊职责（LLM 驱动，根据材料创意生成物品）。"""

    name: str


############################################################################################################
@final
@register_component_type
class DrawPileComponent(MutableComponent):
    """战斗内抽牌堆；Draw 阶段 FIFO 消耗，耗尽时自动将 DiscardPile 洗牌补入；存放 DeckComponent 原始牌的 model_copy() 副本，战斗结束后由 CombatPileTeardownSystem 清空。"""

    name: str
    cards: List[Card]  # FIFO 消耗，耗尽时由 DiscardPile 洗牌补充


############################################################################################################
@final
@register_component_type
class ExhaustPileComponent(MutableComponent):
    """消耗堆；存放主动弃置的自有牌副本，战斗内永久移出抽牌循环；战斗结束后由 CombatPileTeardownSystem 清空。"""

    name: str
    cards: List[Card]  # 按时间顺序追加，战斗内只增不减


############################################################################################################
@final
@register_component_type
class DiscardPileComponent(MutableComponent):
    """弃牌堆；出牌使用后或回合末剩余手牌进入此堆，DrawPile 耗尽时洗牌回补；存放副本，战斗结束后由 CombatPileTeardownSystem 清空。"""

    name: str
    cards: List[Card]  # 按时间顺序追加，DrawPile 耗尽时整体洗牌移入 DrawPile


############################################################################################################
@final
@register_component_type
class DeckComponent(MutableComponent):
    """跨战斗持久牌库；战斗外唯一权威来源。战斗开始时由 DeckGenerationSystem 生成并锁定原始牌，战斗期间只读；战斗子堆流转的均为 model_copy() 副本。keywords 为卡牌生成关键词约束，指导 LLM 按特定风格生成手牌，运行时不可变。"""

    name: str
    cards: List[Card]  # 跨战斗累积；每次触发 GenerateDeckAction 追加新生成的牌
    keywords: List[str]  # 卡牌生成关键词约束，运行时不可变


############################################################################################################
@final
@register_component_type
class InventoryComponent(MutableComponent):
    """随身背包；存储角色当前携带的道具列表。"""

    name: str
    items: List[AnyItem]  # 当前携带的道具


############################################################################################################
@final
@register_component_type
class StorageComponent(MutableComponent):
    """储物箱；存储角色全部道具，为备用库存；初始内容来自蓝图 items。"""

    name: str
    items: List[AnyItem]  # 全部库存道具


############################################################################################################
@final
@register_component_type
class CombatLootComponent(MutableComponent):
    """战斗战利品背包；战斗胜利后由 CombatLootSystem 写入，调用 collect_combat_loot() 后合并至 InventoryComponent 并移除。"""

    name: str
    items: List[AnyItem]  # 本场战斗从怪物处获得的战利品（实践中为 MaterialItem）


############################################################################################################


@final
@register_component_type
class CostumeComponent(MutableComponent):
    """时装组件，记录当前穿戴的时装（CostumeItem）"""

    name: str
    item: CostumeItem


############################################################################################################
@final
@register_component_type
class EquippedGearComponent(MutableComponent):
    """装备组件，记录当前装备中的武器/护甲（GearItem）。"""

    name: str
    item: GearItem
