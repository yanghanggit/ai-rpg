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
class RuntimeComponent(Component):
    name: str
    runtime_index: int
    uuid: str


############################################################################################################
# 记录kick off原始信息
@final
@register_component_type
class KickOffComponent(Component):
    name: str
    content: str


############################################################################################################
# 标记kick off已经完成
@final
@register_component_type
class KickOffDoneComponent(Component):
    name: str
    response: str


############################################################################################################
# 例如，世界级的entity就标记这个组件
@final
@register_component_type
class WorldComponent(Component):
    name: str


############################################################################################################
# 场景标记
@final
@register_component_type
class StageComponent(Component):
    name: str
    character_sheet_name: str


############################################################################################################
# 角色标记
@final
@register_component_type
class ActorComponent(Component):
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
# 玩家标记
@final
@register_component_type
class PlayerOnlyStageComponent(Component):
    name: str


############################################################################################################
# 摧毁Entity标记
@final
@register_component_type
class DestroyComponent(Component):
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
# Stage专用，标记该Stage是Home
@final
@register_component_type
class HomeComponent(Component):
    name: str


############################################################################################################
# Stage专用，标记该Stage是Dungeon
@final
@register_component_type
class DungeonComponent(Component):
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
    """
    以下是针对卡牌游戏中 牌组、弃牌堆、抽牌堆、手牌 的类名设计建议，结合常见游戏术语和编程习惯：
    方案 4：极简统一型
    组件	类名	说明
    牌组	Deck	直接命名为 Deck，表示通用牌组。
    抽牌堆	DrawDeck	与 Deck 统一，通过前缀区分功能。
    弃牌堆	DiscardDeck	同上，保持命名一致性。
    手牌	Hand	简洁无冗余。
    """

    name: str
    cards: List[Card]
    round: int


############################################################################################################
# 死亡标记
@final
@register_component_type
class DeathComponent(Component):
    name: str


############################################################################################################
# 新版本的重构！
@final
@register_component_type
class CombatStatsComponent(MutableComponent):
    name: str
    stats: CharacterStats
    status_effects: List[StatusEffect]


############################################################################################################


@final
@register_component_type
class InventoryComponent(MutableComponent):
    name: str
    items: List[Item]  # 物品列表，存储物品名称

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
    name: str
    skills: List[Skill]  # 技能列表

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
