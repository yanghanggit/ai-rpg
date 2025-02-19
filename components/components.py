from typing import Any, Dict, Final, NamedTuple, List, final
from components.registry import register_component_class


# 全局唯一标识符
@final
@register_component_class
class GUIDComponent(NamedTuple):
    name: str
    GUID: int


############################################################################################################
# 标记agent连接完成
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
class KickOffFlagComponent(NamedTuple):
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
# 场景可以产生actor的孵化器
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


############################################################################################################
# 玩家标记
@final
@register_component_class
class PlayerComponent(NamedTuple):
    name: str


############################################################################################################
# 摧毁Entity标记
@final
@register_component_class
class DestroyComponent(NamedTuple):
    name: str


############################################################################################################
# 自动规划的标记 planning
@final
@register_component_class
class PlanningFlagComponent(NamedTuple):
    name: str


############################################################################################################
# 基础形态。，用于和衣服组成完整的外观信息。如果是动物等，就是动物的外观信息
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
# 标记进入新的
@final
@register_component_class
class EnterStageFlagComponent(NamedTuple):
    name: str
    enter_stage: str


############################################################################################################
# RPG游戏的属性组件
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
# RPG游戏的当前武器组件
@final
@register_component_class
class WeaponComponent(NamedTuple):
    name: str
    prop_name: str


############################################################################################################
# RPG游戏的当前衣服组件
@final
@register_component_class
class ClothesComponent(NamedTuple):
    name: str
    prop_name: str


############################################################################################################
# 每一局的消息记录下来，为了处理archives的问题
@final
@register_component_class
class RoundEventsRecordComponent(NamedTuple):
    name: str
    events: List[str]


############################################################################################################
# 技能
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
# 直接技能的标记。如果标记这个，world_skill_system 将不会进行推理。
@final
@register_component_class
class DirectSkillFlagComponent(NamedTuple):
    name: str
    skill_name: str


############################################################################################################


# # 场景可以用的所有动作
# COMPONENTS_REGISTRY: Final[Dict[str, Any]] = {
#     GUIDComponent.__name__: GUIDComponent,
#     AgentPingFlagComponent.__name__: AgentPingFlagComponent,
#     SystemMessageComponent.__name__: SystemMessageComponent,
#     KickOffMessageComponent.__name__: KickOffMessageComponent,
#     KickOffFlagComponent.__name__: KickOffFlagComponent,
#     WorldSystemComponent.__name__: WorldSystemComponent,
#     StageComponent.__name__: StageComponent,
#     StageGraphComponent.__name__: StageGraphComponent,
#     StageSpawnerComponent.__name__: StageSpawnerComponent,
#     StageEnvironmentComponent.__name__: StageEnvironmentComponent,
#     StageStaticFlagComponent.__name__: StageStaticFlagComponent,
#     ActorComponent.__name__: ActorComponent,
#     PlayerComponent.__name__: PlayerComponent,
#     DestroyComponent.__name__: DestroyComponent,
#     PlanningFlagComponent.__name__: PlanningFlagComponent,
#     BaseFormComponent.__name__: BaseFormComponent,
#     FinalAppearanceComponent.__name__: FinalAppearanceComponent,
#     EnterStageFlagComponent.__name__: EnterStageFlagComponent,
#     AttributesComponent.__name__: AttributesComponent,
#     WeaponComponent.__name__: WeaponComponent,
#     ClothesComponent.__name__: ClothesComponent,
#     RoundEventsRecordComponent.__name__: RoundEventsRecordComponent,
#     SkillComponent.__name__: SkillComponent,
#     DirectSkillFlagComponent.__name__: DirectSkillFlagComponent,
# }
