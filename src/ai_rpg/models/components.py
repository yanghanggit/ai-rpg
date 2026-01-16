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

    Attributes:
        name: 世界系统名称
    """

    name: str
