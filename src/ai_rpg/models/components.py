"""ECS 组件定义。添加到实体后由对应系统读取处理。"""

from typing import List, final
from ..entitas.components import Component, MutableComponent
from .cards import Card, StatusEffect
from .entities import (
    AnyItem,
    Keyword,
    CharacterStats,
)
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
class PlayerOnlyStageComponent(Component):
    """标记场景为玩家专属传送目标。"""

    name: str


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
class AllyComponent(Component):
    """标记角色属于友方阵营。"""

    name: str


############################################################################################################
@final
@register_component_type
class ExpeditionMemberComponent(Component):
    """标记角色为当前地下城远征队活跃成员（AllyComponent 的子集，留守盟友不持有此组件）。"""

    name: str
    dungeon_name: str  # 当前参与的地下城名称


############################################################################################################
@final
@register_component_type
class ExpeditionRosterComponent(Component):
    """挂载在玩家实体，记录本次远征预选同伴名单；为空时玩家独自冒险。"""

    name: str
    members: List[str]  # 其他远征队员名称（不含玩家自身）


############################################################################################################
@final
@register_component_type
class EnemyComponent(Component):
    """标记角色属于敌方阵营。"""

    name: str


############################################################################################################
@final
@register_component_type
class HandComponent(MutableComponent):
    """存储角色当前手牌与所在回合数。"""

    name: str
    cards: List[Card]
    round: int  # 当前回合数


############################################################################################################
@final
@register_component_type
class RoundStatsComponent(MutableComponent):
    """本回合动态战斗属性；每回合开始由 CharacterStats 初始化，回合结束清除。"""

    name: str
    energy: int  # 本回合有效行动次数（可被状态效果修改）
    block: int  # 本回合格挡值（出牌累加，伤害结算时优先抵消，初值 0）


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
class InventoryComponent(MutableComponent):
    """存储角色背包物品列表。"""

    name: str
    items: List[AnyItem]


############################################################################################################
@final
@register_component_type
class EquipmentComponent(MutableComponent):
    """以名称引用记录角色当前装备槽；数据唯一来源为 InventoryComponent，空字符串表示未装备。"""

    name: str
    weapon: str = ""
    armor: str = ""
    accessory: str = ""


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
class DrawDeckComponent(MutableComponent):
    """跨战斗持续累积的可重抽历史牌池；Draw 阶段 FIFO 消耗，回合结束将剩余手牌归还队尾。"""

    name: str
    cards: List[Card]  # FIFO 消耗，回合结束归还


############################################################################################################
@final
@register_component_type
class DiscardDeckComponent(MutableComponent):
    """弃牌归档池；仅用于统计与展示，不参与抽牌逻辑。"""

    name: str
    cards: List[Card]  # 按时间顺序追加，只增不减


############################################################################################################
@final
@register_component_type
class PlayedDeckComponent(MutableComponent):
    """出牌正式归档池；仅归档 `card.source == actor_name` 的自有牌，外来塞入牌丢弃。"""

    name: str
    cards: List[Card]  # 按时间顺序追加，只增不减


############################################################################################################
@final
@register_component_type
class KeywordComponent(Component):
    """存储角色卡牌生成关键词约束，指导 LLM 按特定风格生成手牌；运行时不可变。"""

    name: str
    keywords: List[Keyword]


############################################################################################################
@final
@register_component_type
class AffixSealedComponent(Component):
    """卡牌词条：封印。带有此词条的卡牌不可被出牌，也不可被弃牌。"""

    description: str
