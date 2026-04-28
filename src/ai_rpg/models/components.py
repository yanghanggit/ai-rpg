"""ECS 组件定义模块

定义游戏中所有实体的组件类型，包括：
- 实体标识和生命周期管理
- 类型标记（世界系统、场景、角色）
- 游戏状态（战斗属性、背包、技能）
- 阵营和行为控制
"""

from typing import List, final
from ..entitas.components import Component, MutableComponent
from .combat import Card, StatusEffect
from .entities import (
    AnyItem,
    Archetype,
    CharacterStats,
)
from .registry import register_component_type


############################################################################################################
@final
@register_component_type
class IdentityComponent(Component):
    """实体身份标识组件

    为每个实体提供唯一标识和创建顺序信息，用于实体检索、序列化排序等基础功能。

    Attributes:
        name: 实体名称（游戏内可读标识）
        creation_order: 实体创建顺序索引（用于序列化时保证顺序一致性）
        entity_id: 实体全局唯一标识符（UUID格式）
    """

    name: str
    creation_order: int
    entity_id: str


############################################################################################################
@final
@register_component_type
class WorldComponent(Component):
    """世界系统标记组件

    标记实体为世界系统类型，用于全局功能和系统级行为（如玩家行动审计）。

    Attributes:
        name: 世界系统名称
    """

    name: str


############################################################################################################
@final
@register_component_type
class StageComponent(Component):
    """场景标记组件

    标记实体为场景类型，记录场景的基础配置信息。

    Attributes:
        name: 场景名称
        character_sheet_name: 场景配置表名称
    """

    name: str
    character_sheet_name: str


############################################################################################################
@final
@register_component_type
class ActorComponent(Component):
    """角色标记组件

    标记实体为角色类型，记录角色的基础信息和当前位置。

    Attributes:
        name: 角色名称
        character_sheet_name: 角色配置表名称
        current_stage: 当前所在场景名称
    """

    name: str
    character_sheet_name: str
    current_stage: str


############################################################################################################
# 场景环境描述组件
@final
@register_component_type
class StageDescriptionComponent(Component):
    """场景环境描述组件

    存储场景的环境叙述信息，由AI根据场景初始设定和当前状态动态生成。
    用于为角色行动规划、战斗初始化等系统提供场景上下文。

    Attributes:
        name: 场景名称（实体标识）
        narrative: 场景环境的叙述性描述文本
    """

    name: str
    narrative: str


############################################################################################################
# 玩家标记
@final
@register_component_type
class PlayerComponent(Component):
    """玩家角色标记组件

    标记角色实体由玩家控制，而非AI系统。游戏中有且仅有一个玩家角色。

    使用场景：
        - 远征队组建时必须包含玩家
        - 区分玩家控制和AI控制的角色
        - 家园行动规划时排除玩家（玩家由用户直接控制）
        - 地下城结束时玩家传送到专属场景

    Attributes:
        player_name: 玩家名称
    """

    player_name: str


############################################################################################################
@final
@register_component_type
class PlayerOnlyStageComponent(Component):
    """玩家专属场景标记组件

    标记场景为玩家专属，用于地下城结束或特殊情况下的玩家传送目标。

    Attributes:
        name: 场景名称
    """

    name: str


############################################################################################################
@final
@register_component_type
class DestroyComponent(Component):
    """实体销毁标记组件

    标记实体需要被销毁，系统将在下一帧自动移除带有此组件的实体。

    Attributes:
        name: 实体名称
    """

    name: str


############################################################################################################
# 角色外观信息
@final
@register_component_type
class AppearanceComponent(Component):
    """角色外观描述组件

    Attributes:
        name: 角色名称
        base_body: 基础身体形态描述
        appearance: 最终外观描述，由LLM基于base_body和装备生成
    """

    name: str
    base_body: str
    appearance: str


############################################################################################################
@final
@register_component_type
class HomeComponent(Component):
    """家园场景标记组件

    标记场景为家园类型，用于区分家园场景和地下城场景。

    Attributes:
        name: 场景名称
    """

    name: str


############################################################################################################
@final
@register_component_type
class DungeonComponent(Component):
    """地下城场景标记组件

    标记场景为地下城类型，用于区分地下城场景和家园场景。

    Attributes:
        name: 场景名称
    """

    name: str


############################################################################################################
@final
@register_component_type
class AllyComponent(Component):
    """盟友阵营标记组件

    标记角色实体属于玩家友方阵营。在地下城战斗系统中用于区分敌我阵营。
    带有此组件的角色被视为友方单位，可以与敌方单位（EnemyComponent）进行战斗。

    使用场景：
        - 战斗系统中识别友方单位，构建攻击目标列表
        - 判断角色间的阵营关系（同为友方视为友方，对敌方视为敌方）
        - 地下城推进时识别所有友方实体进行集体移动
        - 战斗归档时统计友方战斗数据

    Attributes:
        name: 角色名称（实体标识）
    """

    name: str


############################################################################################################
@final
@register_component_type
class ExpeditionMemberComponent(Component):
    """地下城远征队成员标记组件

    标记角色实体是当前地下城远征队的活跃成员。用于区分可参与地下城冒险的盟友和留守的盟友。

    设计背景：
        并非所有盟友（AllyComponent）都能参与每次地下城探险，远征队有人数限制。
        此组件标记被选中参与当前地下城冒险的角色，是AllyComponent的子集。

    使用场景：
        - 地下城推进时识别需要集体移动的远征队成员
        - 战斗初始化时确定参战的友方单位
        - 远征队管理界面显示当前队伍成员
        - 经验值、战利品分配时确定分配对象
        - 远征队人数限制检查

    关系说明：
        ExpeditionMemberComponent ⊂ AllyComponent
        拥有此组件的角色必定拥有AllyComponent
        拥有AllyComponent的角色不一定拥有此组件（可能在家园留守）

    Attributes:
        name: 角色名称（实体标识）
        dungeon_name: 当前参与的地下城名称
    """

    name: str
    dungeon_name: str  # 记录参与的地下城，便于多地下城管理


############################################################################################################
@final
@register_component_type
class ExpeditionRosterComponent(Component):
    """远征队名单组件

    挂载在玩家实体上，记录玩家为本次地下城远征预先选定的同伴名单。
    _select_expedition_members 依据此名单决定哪些盟友获得 ExpeditionMemberComponent。

    规则：
        - 玩家自身无条件参与远征，name 字段存玩家名称
        - members 中的名字为其他同伴（非玩家）的角色名称
        - members 为空或组件不存在时，玩家独自冒险

    Attributes:
        name: 玩家角色名称
        members: 其他远征队员的名称列表（不含玩家自身）
    """

    name: str
    members: List[str]


############################################################################################################
@final
@register_component_type
class EnemyComponent(Component):
    """敌方阵营标记组件

    标记角色实体属于敌对阵营。在地下城战斗系统中用于区分敌我阵营。
    带有此组件的角色被视为敌方单位，是友方单位（AllyComponent）的攻击目标。

    使用场景：
        - 战斗系统中识别敌方单位，作为友方的可攻击目标
        - 判断角色间的阵营关系（同为敌方视为友方，对友方视为敌方）
        - 战斗结算时统计敌方存活/阵亡数量判断战斗胜负
        - 敌方AI系统筛选需要进行决策的敌方角色

    Attributes:
        name: 角色名称（实体标识）
    """

    name: str


############################################################################################################
@final
@register_component_type
class HandComponent(MutableComponent):
    """手牌组件

    存储角色当前手牌和回合信息。

    备注：卡牌游戏命名规则
        - 牌组：Deck
        - 抽牌堆：DrawDeck
        - 弃牌堆：DiscardDeck
        - 手牌：Hand

    Attributes:
        name: 角色名称
        cards: 手牌列表
        round: 当前回合数
    """

    name: str
    cards: List[Card]
    round: int


############################################################################################################
@final
@register_component_type
class RoundStatsComponent(MutableComponent):
    """回合动态属性组件

    存储角色本回合的动态战斗属性，在每回合开始时由 CharacterStats（基础值 + 装备加成）初始化，
    回合结束后随 clear_round_state 清除。回合内可被状态效果等系统修改，以实现动态改变能量/速度的玩法。

    与 CharacterStats（不可变基础值）的关系：
        CharacterStats.energy/speed 为只读基础值，本组件为运行时可变副本。

    Attributes:
        name: 角色名称
        energy: 本回合有效行动次数（初值来自 compute_character_stats，回合内可变）
        speed: 本回合有效速度（初值来自 compute_character_stats，回合内可变）
        block: 本回合格挡值（来自出牌时 Card.block 的累加，伤害结算时优先抵消，初值为 0）
    """

    name: str
    energy: int
    # speed: int
    block: int


############################################################################################################
@final
@register_component_type
class DeathComponent(Component):
    """死亡标记组件

    标记角色实体已死亡，用于战斗系统中排除死亡角色。

    Attributes:
        name: 角色名称
    """

    name: str


############################################################################################################
@final
@register_component_type
class CharacterStatsComponent(MutableComponent):
    """战斗属性组件

    存储角色的战斗属性，用于战斗系统计算。
    状态效果已迁移至 CombatStatusEffectsComponent。

    Attributes:
        name: 角色名称
        stats: 角色属性（生命值、攻击力、防御力等）
    """

    name: str
    stats: CharacterStats


############################################################################################################


@final
@register_component_type
class StatusEffectsComponent(MutableComponent):
    """战斗状态效果组件

    存储角色的状态效果列表，用于战斗系统计算。

    Attributes:
        name: 角色名称
        status_effects: 状态效果列表
    """

    name: str
    status_effects: List[StatusEffect]


############################################################################################################
@final
@register_component_type
class InventoryComponent(MutableComponent):
    """背包组件

    存储角色的物品列表，提供物品查询功能。

    Attributes:
        name: 角色名称
        items: 物品列表
    """

    name: str
    items: List[AnyItem]


############################################################################################################
@final
@register_component_type
class EquipmentComponent(MutableComponent):
    """当前装备状态组件

    以名称引用的方式记录角色当前穿戴的装备，InventoryComponent 是数据唯一来源，
    本组件仅持有名称字符串，不复制物品数据。

    每个槽位存储单个物品名称（空字符串表示该槽未装备）。

    Attributes:
        name: 角色名称
        weapon: 当前装备的武器名称（引用 InventoryComponent 中的 Item.name，空字符串表示未装备）
        armor: 当前装备的套装名称（引用 InventoryComponent 中的 Item.name，空字符串表示未装备）
        accessory: 当前装备的饰品名称（引用 InventoryComponent 中的 Item.name，空字符串表示未装备）
    """

    name: str
    weapon: str = ""
    armor: str = ""
    accessory: str = ""


############################################################################################################
@final
@register_component_type
class PlayerActionAuditComponent(Component):
    """玩家行动审计组件。

    标记组件，标识世界系统实体具有玩家行动审计功能。

    Attributes:
        name: 世界系统名称
    """

    name: str


############################################################################################################
@final
@register_component_type
class DungeonGenerationComponent(Component):
    """地下城生成组件。

    标记组件，标识世界系统实体具有地下城图片生成职责（文生图）。

    Attributes:
        name: 世界系统名称
    """

    name: str


############################################################################################################
@final
@register_component_type
class DrawDeckComponent(MutableComponent):
    """可重抽历史牌池组件

    存储角色下一回合可重复抽取的历史卡牌。
    在 actor 创建时以空列表初始化，跨战斗持续累积，随实体销毁自然消失。

    累积规则：
        - Draw 阶段 FIFO 从队首消耗（最多 max_num_cards - 1 张）作为历史牌直接进入手牌
        - 每回合结束清除 HandComponent 时，剩余手牌 extend 到此组件队尾

    Attributes:
        name: 角色名称
        cards: 可重抽卡牌列表（FIFO 消耗，回合结束归还）
    """

    name: str
    cards: List[Card]


############################################################################################################
@final
@register_component_type
class DiscardDeckComponent(MutableComponent):
    """已打出卡牌归档组件

    存储角色在地下城过程中所有已打出的卡牌，仅用于统计与展示，不参与抽牌逻辑。
    在 actor 创建时以空列表初始化，跨战斗持续累积，随实体销毁自然消失。

    累积规则：
        - 每次出牌后，被打出的 Card 从 HandComponent 移除并 append 到此组件

    Attributes:
        name: 角色名称
        cards: 已打出卡牌列表（按时间顺序追加，只增不减）
    """

    name: str
    cards: List[Card]


############################################################################################################
@final
@register_component_type
class ArchetypeComponent(Component):
    """卡牌原型约束组件

    存储角色的卡牌生成原型约束，在战斗中指导 LLM 按特定风格生成手牌。
    数据来源于 Actor.archetypes，在实体创建时挂载，运行时不可变。

    Attributes:
        name: 角色名称
        archetypes: 原型约束列表
    """

    name: str
    archetypes: List[Archetype]
