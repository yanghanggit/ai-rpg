from typing import NamedTuple, List, final


# 全局唯一标识符
@final
class GUIDComponent(NamedTuple):
    name: str
    GUID: int


# 标记agent连接完成
@final
class AgentPingFlagComponent(NamedTuple):
    name: str


# 记录kick off原始信息
@final
class KickOffContentComponent(NamedTuple):
    name: str
    content: str


# 标记kick off已经完成
@final
class KickOffFlagComponent(NamedTuple):
    name: str


# 例如，世界级的entity就标记这个组件
@final
class WorldComponent(NamedTuple):
    name: str


# 场景标记
@final
class StageComponent(NamedTuple):
    name: str


# 场景可以去往的地方
@final
class StageGraphComponent(NamedTuple):
    name: str
    stage_graph: List[str]


# 场景可以产生actor的孵化器
@final
class StageSpawnerComponent(NamedTuple):
    name: str
    spawners: List[str]


# 角色标记
@final
class ActorComponent(NamedTuple):
    name: str
    current_stage: str


# 玩家标记
@final
class PlayerComponent(NamedTuple):
    name: str


# 摧毁Entity标记
@final
class DestroyComponent(NamedTuple):
    name: str


# 自动规划的标记
@final
class PlanningAllowedComponent(NamedTuple):
    name: str


# 基础形态。，用于和衣服组成完整的外观信息。如果是动物等，就是动物的外观信息
@final
class BaseFormComponent(NamedTuple):
    name: str
    base_form: str


# 角色外观信息
@final
class FinalAppearanceComponent(NamedTuple):
    name: str
    final_appearance: str


# 标记进入新的舞台
@final
class EnterStageFlagComponent(NamedTuple):
    name: str
    enter_stage: str


# RPG游戏的属性组件
@final
class AttributesComponent(NamedTuple):
    name: str
    maxhp: int
    hp: int
    attack: int
    defense: int


# RPG游戏的当前武器组件
@final
class WeaponComponent(NamedTuple):
    name: str
    propname: str


# RPG游戏的当前衣服组件
@final
class ClothesComponent(NamedTuple):
    name: str
    propname: str


# 每一局的消息记录下来，为了处理archives的问题
@final
class RoundEventsRecordComponent(NamedTuple):
    name: str
    events: List[str]


# 技能
@final
class SkillComponent(NamedTuple):
    name: str
    command: str
    skill_name: str
    stage: str
    targets: List[str]
    skill_accessory_props: List[str]
    world_harmony_inspector_tag: str
    world_harmony_inspector_content: str
    world_harmony_inspector_value: int
