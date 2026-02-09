"""ECS 组件定义模块

定义游戏中所有实体的组件类型，包括：
- 实体标识和生命周期管理
- 类型标记（世界系统、场景、角色）
- 游戏状态（战斗属性、背包、技能）
- 阵营和行为控制
"""

from typing import List, final
from ..entitas.components import Component, MutableComponent
from .dungeon import Card, StatusEffect
from .entities import (
    CharacterStats,
    Item,
    Skill,
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
class KickOffComponent(Component):
    """实体启动提示组件

    存储实体启动时发送给 LLM 的初始化提示消息。用于生成角色的自我认知、
    场景的环境描述或世界系统的初始状态。

    Attributes:
        name: 实体名称（实体标识）
        prompt: 启动提示内容（发送给 LLM 的提示词）
    """

    name: str
    prompt: str


############################################################################################################
@final
@register_component_type
class KickOffCompleteComponent(Component):
    """实体启动完成标记组件

    标记实体已完成启动初始化流程。用于筛选时排除已初始化的实体，
    避免重复执行启动流程。同时保存 LLM 生成的初始化响应供后续使用。

    Attributes:
        name: 实体名称（实体标识）
        initialization_result: LLM 生成的初始化响应内容
            - 角色实体：自我认知和目标确认的文本
            - 场景实体：环境描述的叙述文本
            - 世界系统：系统初始状态说明
    """

    name: str
    initialization_result: str


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
class HandComponent(Component):
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
class CombatStatsComponent(MutableComponent):
    """战斗属性组件

    存储角色的战斗属性和状态效果，用于战斗系统计算。

    Attributes:
        name: 角色名称
        stats: 角色属性（生命值、攻击力、防御力等）
        status_effects: 状态效果列表
    """

    name: str
    stats: CharacterStats
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
    items: List[Item]

    # 获取物品
    def find_item(self, item_name: str) -> Item | None:
        list_items = self.get_items([item_name])
        if len(list_items) > 0:
            return list_items[0]
        return None

    # 获取多个物品
    def get_items(self, item_names: List[str]) -> List[Item]:
        found_items = []
        for item in self.items:
            if item.name in item_names:
                found_items.append(item)
        return found_items


############################################################################################################
@final
@register_component_type
class SkillBookComponent(MutableComponent):
    """技能书组件

    存储角色的技能列表，提供技能查询功能。

    Attributes:
        name: 角色名称
        skills: 技能列表
    """

    name: str
    skills: List[Skill]

    # 查找技能
    def find_skill(self, skill_name: str) -> Skill | None:
        for skill in self.skills:
            if skill.name == skill_name:
                return skill
        return None

    # 获取多个技能
    def get_skills(self, skill_names: List[str]) -> List[Skill]:
        return [skill for skill in self.skills if skill.name in skill_names]


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
