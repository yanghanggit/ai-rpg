from typing import Any, FrozenSet, NamedTuple, List


class ActionComponent(NamedTuple):
    name: str
    values: List[str]


# 场景环境的描述
class StageNarrateAction(ActionComponent):
    pass


# 内心独白
class MindVoiceAction(ActionComponent):
    pass


# 场景内广播
class BroadcastAction(ActionComponent):
    pass


# 私下交流
class WhisperAction(ActionComponent):
    pass


# 对谁说（场景内其他角色能听到）
class SpeakAction(ActionComponent):
    pass


# 标签
class TagAction(ActionComponent):
    pass


# 死亡
class DeadAction(ActionComponent):
    pass


# 离开当前场景并去往
class GoToAction(ActionComponent):
    pass


# 从场景内可以拾取道具
class PickUpPropAction(ActionComponent):
    pass


# 从目标角色处偷取
class StealPropAction(ActionComponent):
    pass


# 将道具交给目标角色
class GivePropAction(ActionComponent):
    pass


# 行为动作与技能动作
class BehaviorAction(ActionComponent):
    pass


# 技能目标动作
class SkillTargetAction(ActionComponent):
    pass


# 技能动作
class SkillAction(ActionComponent):
    pass


# 使用技能道具动作
class SkillUsePropAction(ActionComponent):
    pass


# 世界技能系统规则动作
class WorldSkillSystemRuleAction(ActionComponent):
    pass


# 更新外观
class UpdateAppearanceAction(ActionComponent):
    pass


# 处理伤害逻辑
class DamageAction(ActionComponent):
    pass


# 装备道具
class EquipPropAction(ActionComponent):
    pass


# 场景内销毁道具
class RemovePropAction(ActionComponent):
    pass


CONVERSATION_ACTIONS_REGISTER: FrozenSet[type[Any]] = frozenset(
    {TagAction, MindVoiceAction, SpeakAction, BroadcastAction, WhisperAction}
)

# 场景可以用的所有动作
STAGE_AVAILABLE_ACTIONS_REGISTER: FrozenSet[type[Any]] = (
    frozenset(
        {
            StageNarrateAction,
            RemovePropAction,
            DamageAction,
        }
    )
    | CONVERSATION_ACTIONS_REGISTER
)


# 角色交互类动作
ACTOR_INTERACTIVE_ACTIONS_REGISTER: FrozenSet[type[Any]] = frozenset(
    {
        PickUpPropAction,
        GoToAction,
        StealPropAction,
        GivePropAction,
        BehaviorAction,
        SkillTargetAction,
        SkillAction,
        SkillUsePropAction,
        WorldSkillSystemRuleAction,
        UpdateAppearanceAction,
        DamageAction,
        EquipPropAction,
    }
)

# 角色可以用的所有动作
ACTOR_AVAILABLE_ACTIONS_REGISTER: FrozenSet[type[Any]] = (
    ACTOR_INTERACTIVE_ACTIONS_REGISTER | CONVERSATION_ACTIONS_REGISTER
)
