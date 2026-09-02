"""ECS 组件定义。添加到实体后由对应系统读取处理。"""

from typing import List, final

from ..entitas.components import Component
from .card import Card
from .character_stats import CharacterStats
from .items import AnyItem, CostumeItem, GearItem
from .registry import register_component_type

############################################################################################################
# 每回合固定行动次数（能量）；由 CombatRoundTransitionSystem 用于初始化 RoundStatsComponent，
# 目前所有角色恒定共用该值，不随角色或装备变化。
# DEFAULT_ROUND_ENERGY: Final[int] = 2


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
    """标记实体为世界级实体（全局、唯一、独立于场景）。"""

    name: str


############################################################################################################
@final
@register_component_type
class StageComponent(Component):
    """标记实体为场景类型。"""

    name: str


############################################################################################################
@final
@register_component_type
class ActorComponent(Component):
    """标记实体为角色类型，记录当前所在场景。"""

    name: str
    current_stage: str  # 当前所在场景名称


############################################################################################################
@final
@register_component_type
class StageDescriptionComponent(Component):
    """场景环境叙述，由 AI 根据当前状态动态生成，为行动规划与战斗初始化等系统提供背景信息。"""

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
    """标记场景为副本类型。"""

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
    """标记角色为当前副本队伍活跃成员（NPCComponent 的子集，留守盟友不持有此组件）。"""

    name: str


############################################################################################################
@final
@register_component_type
class PartyRosterComponent(Component):
    """挂载在玩家实体，记录本次副本预选同伴名单；为空时玩家独自冒险。

    roster 即「名单」，对应 CLI 的 roster / roster-add / roster-remove 命令。
    """

    name: str
    members: List[str]  # 其他队伍成员名称（不含玩家自身）


############################################################################################################
@final
@register_component_type
class MonsterComponent(Component):
    """标记角色为怪物（敌方阵营战斗单位）。"""

    name: str


############################################################################################################
@final
@register_component_type
class HandComponent(Component):
    """存储角色当前手牌与所在回合数。"""

    name: str
    cards: List[Card]


############################################################################################################
@final
@register_component_type
class RoundStatsComponent(Component):
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
class CharacterStatsComponent(Component):
    """存储角色战斗属性（HP、攻击力、防御力等）。"""

    name: str
    stats: CharacterStats


############################################################################################################
@final
@register_component_type
class PlayerActionAuditComponent(Component):
    """标记世界实体具有玩家行动审计功能。"""

    name: str


############################################################################################################
@final
@register_component_type
class DungeonGenerationComponent(Component):
    """标记世界实体具有副本图片生成职责。"""

    name: str


############################################################################################################
@final
@register_component_type
class GearWorkshopComponent(Component):
    """标记世界实体具有装备工坊职责（LLM 驱动，仅合成装备）。"""

    name: str


@final
@register_component_type
class ConsumableWorkshopComponent(Component):
    """标记世界实体具有消耗品工坊职责（LLM 驱动，仅合成消耗品）。"""

    name: str


@final
@register_component_type
class CostumeWorkshopComponent(Component):
    """标记世界实体具有时装工坊职责（LLM 驱动，仅制作时装）。"""

    name: str


@final
@register_component_type
class ConsumableArbitratorComponent(Component):
    """标记世界实体具有消耗品使用仲裁职责（LLM 驱动，作为临时 agent 结算消耗品效果）。"""

    name: str


############################################################################################################
@final
@register_component_type
class DungeonDirectorComponent(Component):
    """标记世界实体为副本导演，扮演当前正在游玩的副本，随房间进程积累记忆，副本结束时总结移交世界导演。"""

    name: str


############################################################################################################
@final
@register_component_type
class WorldDirectorComponent(Component):
    """标记世界实体为世界导演（桌游 GM），负责统筹世界演进与新副本创作。"""

    name: str


############################################################################################################
@final
@register_component_type
class DrawPileComponent(Component):
    """战斗内抽牌堆；Draw 阶段 FIFO 消耗，耗尽时自动将 DiscardPile 洗牌补入；存放 DeckComponent 原始牌的 model_copy() 副本，战斗结束后由 CombatPileTeardownSystem 清空。"""

    name: str
    cards: List[Card]  # FIFO 消耗，耗尽时由 DiscardPile 洗牌补充
    retained_cards: List[Card] = (
        []
    )  # retain 牌临时中转队列：回合末由 clear_round_state 写入，下回合 DrawCardsActionSystem 优先取回手牌并计入目标张数


############################################################################################################
@final
@register_component_type
class ExhaustPileComponent(Component):
    """消耗堆；存放主动弃置的自有牌副本，战斗内永久移出抽牌循环；战斗结束后由 CombatPileTeardownSystem 清空。"""

    name: str
    cards: List[Card]  # 按时间顺序追加，战斗内只增不减


############################################################################################################
@final
@register_component_type
class DiscardPileComponent(Component):
    """弃牌堆；出牌使用后或回合末剩余手牌进入此堆，DrawPile 耗尽时洗牌回补；存放副本，战斗结束后由 CombatPileTeardownSystem 清空。"""

    name: str
    cards: List[Card]  # 按时间顺序追加，DrawPile 耗尽时整体洗牌移入 DrawPile


############################################################################################################
@final
@register_component_type
class DeckComponent(Component):
    """跨战斗持久牌库。"""

    name: str
    cards: List[Card]


############################################################################################################
@final
@register_component_type
class CardPoolComponent(Component):
    """卡池：待从中抽取的候选卡牌（默认 3 张，3 选 1）。"""

    name: str
    cards: List[Card]  # 候选卡；抽卡后由后续动作移入牌库并清空本组件


############################################################################################################
@final
@register_component_type
class InventoryComponent(Component):
    """随身背包；存储角色当前携带的道具列表。"""

    name: str
    items: List[AnyItem]  # 当前携带的道具


############################################################################################################
@final
@register_component_type
class StorageComponent(Component):
    """储物箱；存储角色全部道具，为备用库存；初始内容来自蓝图 items。"""

    name: str
    items: List[AnyItem]  # 全部库存道具


############################################################################################################
@final
@register_component_type
class CombatLootComponent(Component):
    """战斗战利品背包；战斗胜利后由 CombatLootSystem 写入，调用 collect_combat_loot() 后合并至 InventoryComponent 并移除。"""

    name: str
    items: List[AnyItem]  # 本场战斗从怪物处获得的战利品（实践中为 MaterialItem）


############################################################################################################


@final
@register_component_type
class WornCostumeComponent(Component):
    """时装组件，记录当前穿戴的时装（CostumeItem）"""

    name: str
    item: CostumeItem


############################################################################################################
@final
@register_component_type
class EquippedGearComponent(Component):
    """战斗中由当前行动者转化、待归还玩家背包的装备暂存列表；可同时存在于多个角色实体上。"""

    name: str
    items: List[GearItem]
