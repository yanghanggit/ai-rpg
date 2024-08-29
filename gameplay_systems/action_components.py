from collections import namedtuple
from typing import List, Dict, Any, Union, FrozenSet, Tuple

################################################ 动作组件： ####################################################################################
# 场景环境的描述
StageNarrateAction = namedtuple("StageNarrateAction", "name action_name values")
# 内心独白
MindVoiceAction = namedtuple("MindVoiceAction", "name action_name values")
# 场景内广播
BroadcastAction = namedtuple("BroadcastAction", "name action_name values")
# 私下交流
WhisperAction = namedtuple("WhisperAction", "name action_name values")
# 对谁说（场景内其他角色能听到）
SpeakAction = namedtuple("SpeakAction", "name action_name values")
# 标签
TagAction = namedtuple("TagAction", "name action_name values")
# 死亡
DeadAction = namedtuple("DeadAction", "name action_name values")
# 离开当前场景并去往
GoToAction = namedtuple("GoToAction", "name action_name values")
# 从场景内可以拾取道具
PickUpPropAction = namedtuple("PickUpPropAction", "name action_name values")
# 从目标角色处偷取
StealPropAction = namedtuple("StealPropAction", "name action_name values")
# 将道具交给目标角色
GivePropAction = namedtuple("GivePropAction", "name action_name values")
# 行为动作与技能动作
BehaviorAction = namedtuple("BehaviorAction", "name action_name values")
SkillTargetAction = namedtuple("SkillTargetAction", "name action_name values")
SkillAction = namedtuple("SkillAction", "name action_name values")
SkillPropAction = namedtuple("SkillPropAction", "name action_name values")


# 更新外观
UpdateAppearanceAction = namedtuple("UpdateAppearanceAction", "name action_name values")

# 处理伤害逻辑
DamageAction = namedtuple("DamageAction", "name action_name values")

# 装备道具
EquipPropAction = namedtuple("EquipPropAction", "name action_name values")
##############################################################################################################################################


# 场景可以用的所有动作
STAGE_AVAILABLE_ACTIONS_REGISTER: FrozenSet[type[Any]] = frozenset(
    {TagAction, MindVoiceAction, WhisperAction, StageNarrateAction, DamageAction}
)


# 角色可以用的所有动作
ACTOR_AVAILABLE_ACTIONS_REGISTER: FrozenSet[type[Any]] = frozenset(
    {
        GoToAction,
        SpeakAction,
        TagAction,
        MindVoiceAction,
        BroadcastAction,
        WhisperAction,
        PickUpPropAction,
        StealPropAction,
        GivePropAction,
        BehaviorAction,
        SkillTargetAction,
        SkillAction,
        SkillPropAction,
        UpdateAppearanceAction,
        DamageAction,
        EquipPropAction,
    }
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
        SkillPropAction,
        UpdateAppearanceAction,
        DamageAction,
        EquipPropAction,
    }
)
