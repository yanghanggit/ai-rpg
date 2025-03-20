from typing import NamedTuple, List, final
from components.registry import register_component_class
from tcg_models.v_0_0_1 import Skill, Effect


# 全局唯一标识符
@final
@register_component_class
class GUIDComponent(NamedTuple):
    name: str
    GUID: int


############################################################################################################
# 标记agent连接完成 TODO:旧组件，用上的时候把这个删了
@final
@register_component_class
class AgentPingFlagComponent(NamedTuple):
    name: str


############################################################################################################
# 记录 系统提示词 的组件
@final
@register_component_class
class SystemMessageComponent(NamedTuple):
    name: str
    content: str


############################################################################################################
# 记录kick off原始信息
@final
@register_component_class
class KickOffMessageComponent(NamedTuple):
    name: str
    content: str


############################################################################################################
# 标记kick off已经完成
@final
@register_component_class
class KickOffDoneFlagComponent(NamedTuple):
    name: str


############################################################################################################
# 例如，世界级的entity就标记这个组件
@final
@register_component_class
class WorldSystemComponent(NamedTuple):
    name: str


############################################################################################################
# 场景标记
@final
@register_component_class
class StageComponent(NamedTuple):
    name: str


############################################################################################################
# 场景可以去往的地方
@final
@register_component_class
class StageGraphComponent(NamedTuple):
    name: str
    stage_graph: List[str]


############################################################################################################
# 场景可以产生actor的孵化器 TODO:旧组件，用上的时候把这个删了
@final
@register_component_class
class StageSpawnerComponent(NamedTuple):
    name: str
    spawners: List[str]


############################################################################################################
# 记录场景的描述 #Environment
@final
@register_component_class
class StageEnvironmentComponent(NamedTuple):
    name: str
    narrate: str
    # story: str


############################################################################################################
# 一旦标记这个，就说明这个场景是静态的，不会发生变化，就是不会参与planning的执行中去。
@final
@register_component_class
class StageStaticFlagComponent(NamedTuple):
    name: str


############################################################################################################
# 角色标记
@final
@register_component_class
class ActorComponent(NamedTuple):
    name: str
    current_stage: str


@final
@register_component_class
class AttributeCompoment(NamedTuple):
    name: str


############################################################################################################
# 玩家标记
@final
@register_component_class
class PlayerActorFlagComponent(NamedTuple):
    name: str


############################################################################################################
# 摧毁Entity标记
@final
@register_component_class
class DestroyFlagComponent(NamedTuple):
    name: str


############################################################################################################
# 自动规划的标记 planning TODO:旧组件，用上的时候把这个删了
@final
@register_component_class
class PlanningFlagComponent(NamedTuple):
    name: str


############################################################################################################
# 基础形态。，用于和衣服组成完整的外观信息。如果是动物等，就是动物的外观信息 TODO:旧组件，用上的时候把这个删了
@final
@register_component_class
class BaseFormComponent(NamedTuple):
    name: str
    base_form: str


############################################################################################################
# 角色外观信息
@final
@register_component_class
class FinalAppearanceComponent(NamedTuple):
    name: str
    final_appearance: str


############################################################################################################
# 标记进入新的场景
@final
@register_component_class
class EnterStageFlagComponent(NamedTuple):
    name: str
    enter_stage: str


############################################################################################################
# RPG游戏的属性组件 TODO:旧组件，用上的时候把这个删了
@final
@register_component_class
class AttributesComponent(NamedTuple):
    name: str
    max_hp: int
    cur_hp: int
    damage: int
    defense: int
    heal: int


############################################################################################################
# RPG游戏的当前武器组件 TODO:旧组件，用上的时候把这个删了
@final
@register_component_class
class WeaponComponent(NamedTuple):
    name: str
    prop_name: str


############################################################################################################
# RPG游戏的当前衣服组件 TODO:旧组件，用上的时候把这个删了
@final
@register_component_class
class ClothesComponent(NamedTuple):
    name: str
    prop_name: str


############################################################################################################
# 每一局的消息记录下来，为了处理archives的问题 TODO:旧组件，用上的时候把这个删了
@final
@register_component_class
class RoundEventsRecordComponent(NamedTuple):
    name: str
    events: List[str]


############################################################################################################
# 技能 TODO:旧组件，用上的时候把这个删了
@final
@register_component_class
class SkillComponent(NamedTuple):
    name: str
    command: str
    skill_name: str
    stage: str
    targets: List[str]
    skill_accessory_props: List[str]
    inspector_tag: str
    inspector_content: str
    inspector_value: int


############################################################################################################
# 直接技能的标记。如果标记这个，world_skill_system 将不会进行推理。 TODO:旧组件，用上的时候把这个删了
@final
@register_component_class
class DirectSkillFlagComponent(NamedTuple):
    name: str
    skill_name: str


############################################################################################################
# Stage专用，标记该Stage是Home
@final
@register_component_class
class HomeStageFlagComponent(NamedTuple):
    name: str


############################################################################################################
# Stage专用，标记该Stage是Dungeon
@final
@register_component_class
class DungeonStageFlagComponent(NamedTuple):
    name: str


############################################################################################################
# Actor专用，标记该Actor是Hero
@final
@register_component_class
class HeroActorFlagComponent(NamedTuple):
    name: str


############################################################################################################
# Actor专用，标记该Actor是Monster
@final
@register_component_class
class MonsterActorFlagComponent(NamedTuple):
    name: str


############################################################################################################
# Actor专用，标记该Actor需要进行角色扮演推理（心理活动，说话...），如有需要，单独列入Plan
@final
@register_component_class
class ActorPlanningPermitFlagComponent(NamedTuple):
    name: str


############################################################################################################
# State专用，标记该State需要进行场景描写推理，如有需要，单独列入Plan
@final
@register_component_class
class StagePlanningPermitFlagComponent(NamedTuple):
    name: str


############################################################################################################
@final
@register_component_class
class SkillCandidateQueueComponent(NamedTuple):
    name: str
    queue: List[Skill]


############################################################################################################
# 战斗中临时使用。
@final
@register_component_class
class CombatAttributesComponent(NamedTuple):
    name: str
    level: int
    hp: int
    max_hp: int
    strength: int
    dexterity: int
    wisdom: int
    physical_attack: int
    physical_defense: int
    magic_attack: int
    magic_defense: int

    @property
    def prompt(self) -> str:
        return f"""当前生命：{self.hp}
最大生命：{self.max_hp}
物理攻击：{self.physical_attack}
物理防御：{self.physical_defense}
魔法攻击：{self.magic_attack}
魔法防御：{self.magic_defense}"""


############################################################################################################
# 战斗中临时使用。
@final
@register_component_class
class CombatEffectsComponent(NamedTuple):
    name: str
    effects: List[Effect]


############################################################################################################
