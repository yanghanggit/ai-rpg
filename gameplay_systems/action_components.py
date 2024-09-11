from collections import namedtuple
from typing import Any, FrozenSet

################################################ 动作组件： ####################################################################################
# 场景环境的描述
StageNarrateAction = namedtuple("StageNarrateAction", "name values")
# 内心独白
MindVoiceAction = namedtuple("MindVoiceAction", "name values")
# 场景内广播
BroadcastAction = namedtuple("BroadcastAction", "name values")
# 私下交流
WhisperAction = namedtuple("WhisperAction", "name values")
# 对谁说（场景内其他角色能听到）
SpeakAction = namedtuple("SpeakAction", "name values")
# 标签
TagAction = namedtuple("TagAction", "name values")
# 死亡
DeadAction = namedtuple("DeadAction", "name values")
# 离开当前场景并去往
GoToAction = namedtuple("GoToAction", "name values")
# 从场景内可以拾取道具
PickUpPropAction = namedtuple("PickUpPropAction", "name values")
# 从目标角色处偷取
StealPropAction = namedtuple("StealPropAction", "name values")
# 将道具交给目标角色
GivePropAction = namedtuple("GivePropAction", "name values")
# 行为动作与技能动作
BehaviorAction = namedtuple("BehaviorAction", "name values")
SkillTargetAction = namedtuple("SkillTargetAction", "name values")
SkillAction = namedtuple("SkillAction", "name values")
SkillUsePropAction = namedtuple("SkillUsePropAction", "name values")
WorldSkillSystemRuleAction = namedtuple("WorldSkillSystemRuleAction", "name values")


# 更新外观
UpdateAppearanceAction = namedtuple("UpdateAppearanceAction", "name values")

# 处理伤害逻辑
DamageAction = namedtuple("DamageAction", "name values")

# 装备道具
EquipPropAction = namedtuple("EquipPropAction", "name values")

# 场景内销毁道具
RemovePropAction = namedtuple("RemovePropAction", "name values")
##############################################################################################################################################


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
