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
# 全局唯一标识符 RunTimeIndexComponent
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
# 记录场景的描述 #Environment
@final
@register_component_type
class EnvironmentComponent(Component):
    name: str
    description: str


############################################################################################################
# 玩家标记
@final
@register_component_type
class PlayerComponent(Component):
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
    """角色外观描述组件。

    用于存储和管理角色的外观信息，为AI系统和游戏交互提供视觉描述上下文。
    此组件是角色实体的必要组件之一，支持基于基础形态和装备的动态外观生成。

    设计思路:
        1. base_body: 角色的基础身体形态（如穿内衣时的样子），作为外观生成的基础
        2. appearance: 最终的外观描述，由 LLM 综合 base_body 和装备信息生成
        3. 装备信息从 InventoryComponent 中获取（未来扩展）

    Attributes:
        name: 角色名称，用于标识该外观信息所属的角色
        base_body: 基础身体形态描述（身高、体型、肤色、发色等天生特征）
        appearance: 最终外观文本描述，包含基础形态、着装、饰品等完整视觉信息

    使用场景:
        - 场景描述生成：通过 `get_actor_appearances_on_stage()` 获取场景中所有角色的外观
        - 战斗系统：在战斗初始化时向AI提供其他角色的外观信息，辅助决策
        - 对话系统：增强AI对话的上下文感知，提升交互真实感
        - 装备系统：装备变化时，基于 base_body 和新装备重新生成 appearance（未来扩展）

    Example:
        >>> # 初始化角色外观
        >>> actor_entity.add(
        ...     AppearanceComponent,
        ...     "艾莉亚",
        ...     "身材修长的年轻精灵，银色长发，翠绿双眸",  # base_body
        ...     "一位年轻的精灵游侠，银色长发，身穿绿色斗篷"  # appearance
        ... )
        >>>
        >>> # 装备变化时更新外观（未来扩展）
        >>> appearance = actor_entity.get(AppearanceComponent)
        >>> new_appearance = await generate_appearance(
        ...     base_body=appearance.base_body,
        ...     equipped_items=["钢铁护甲", "精灵长弓"]
        ... )
        >>> actor_entity.replace(
        ...     AppearanceComponent,
        ...     actor_entity.name,
        ...     appearance.base_body,
        ...     new_appearance
        ... )

    Note:
        - 使用 `@final` 装饰器防止被继承修改
        - 使用 MutableComponent 支持外观动态更新
        - base_body 通常在角色创建后保持不变
        - appearance 可随装备变化而重新生成
        - 只有存活且具有此组件的角色才会在场景描述中显示外观
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
# Actor专用，标记该Actor是盟友
@final
@register_component_type
class AllyComponent(Component):
    name: str


############################################################################################################
# Actor专用，标记该Actor是Monster
@final
@register_component_type
class EnemyComponent(Component):
    name: str


############################################################################################################


# 手牌组件。
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
    play_card
    draw_card
    """

    name: str
    cards: List[Card]


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

    @property
    def stats_prompt(self) -> str:
        return f"HP:{self.stats.hp}/{self.stats.max_hp} | 攻击:{self.stats.attack} | 防御:{self.stats.defense}"

    @property
    def status_effects_prompt(self) -> str:
        if len(self.status_effects) == 0:
            return "- 无"
        return "\n".join(
            [f"- {effect.name}: {effect.description}" for effect in self.status_effects]
        )


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

    # 打包成提示词型的字符串
    @property
    def list_items_prompt(self) -> str:
        if len(self.items) == 0:
            return "- 无"
        return "\n".join(
            [
                f"- {item.name}: {item.description}, 数量: {item.count}"
                for item in self.items
            ]
        )


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

    # 生成技能列表提示词
    @property
    def list_skills_prompt(self) -> str:
        if len(self.skills) == 0:
            return "- 无"
        return "\n".join(
            [f"- {skill.name}: {skill.description}" for skill in self.skills]
        )


############################################################################################################
@final
@register_component_type
class PlayerActionAuditComponent(Component):
    """玩家行动审计组件。

    标记组件，标识世界系统实体具有玩家行动审计功能。

    审计标准:
        - 拒绝法律与道德禁止的内容（暴力教唆、违法行为、歧视性内容等）
        - 拒绝破坏游戏世界观的内容（现实科技、元游戏语言、系统操作等）
        - 允许符合游戏世界观的角色互动和游戏内合理行为

    Attributes:
        name: 世界系统名称

    Note:
        审核不通过时会移除所有动作组件，阻止消息发送。默认采用"安全优先"策略。
    """

    name: str
