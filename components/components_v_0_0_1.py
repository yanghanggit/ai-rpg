from typing import Final, NamedTuple, List, final
from components.registry import register_component_class
from models.v_0_0_1 import Skill, Effect


# 注意，不允许动！
SCHEMA_VERSION: Final[str] = "0.0.1"


# 全局唯一标识符
@final
@register_component_class
class GUIDComponent(NamedTuple):
    name: str
    GUID: int


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
# 记录场景的描述 #Environment
@final
@register_component_class
class StageEnvironmentComponent(NamedTuple):
    name: str
    narrate: str


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
class PlayerActorFlagComponent(NamedTuple):
    name: str


############################################################################################################
# 摧毁Entity标记
@final
@register_component_class
class DestroyFlagComponent(NamedTuple):
    name: str


############################################################################################################
# 角色外观信息
@final
@register_component_class
class AppearanceComponent(NamedTuple):
    name: str
    appearance: str


############################################################################################################
# 标记进入新的场景
@final
@register_component_class
class EnterStageFlagComponent(NamedTuple):
    name: str
    enter_stage: str


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
    hp: float
    max_hp: float
    physical_attack: float
    physical_defense: float
    magic_attack: float
    magic_defense: float

    @property
    def as_prompt(self) -> str:
        return f"""- 当前生命：{self.hp}
- 最大生命：{self.max_hp}
- 物理攻击：{self.physical_attack}
- 物理防御：{self.physical_defense}
- 魔法攻击：{self.magic_attack}
- 魔法防御：{self.magic_defense}"""


############################################################################################################
# 战斗中临时使用。
@final
@register_component_class
class CombatEffectsComponent(NamedTuple):
    name: str
    effects: List[Effect]

    @property
    def as_prompt(self) -> str:
        ret = "- 无"
        if len(self.effects) > 0:
            ret = "\n".join(
                [
                    f"- {effect.name}: {effect.description} (剩余{effect.rounds}回合)"
                    for effect in self.effects
                ]
            )
        return ret


############################################################################################################
