from collections import namedtuple


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
# 攻击
#AttackAction = namedtuple("AttackAction", "name action_name values")
# 死亡
DeadAction = namedtuple("DeadAction", "name action_name values")
# 离开当前场景并去往
GoToAction = namedtuple("GoToAction", "name action_name values")
# 寻找场景内道具
SearchPropAction = namedtuple("SearchPropAction", "name action_name values")
# 从目标角色处偷取
StealPropAction = namedtuple("StealPropAction", "name action_name values")
# 将道具交给目标角色
GivePropAction = namedtuple("GivePropAction", "name action_name values")
# 使用道具
UsePropAction = namedtuple("UsePropAction", "name action_name values")
# 感知场景内的信息（角色与道具）
PerceptionAction = namedtuple("PerceptionAction", "name action_name values")
# 检查自身状态
CheckStatusAction = namedtuple("CheckStatusAction", "name action_name values")
#
BehaviorAction = namedtuple("BehaviorAction", "name action_name values")
TargetAction = namedtuple("TargetAction", "name action_name values")
SkillAction = namedtuple("SkillAction", "name action_name values")
PropAction = namedtuple("PropAction", "name action_name values")

UpdateAppearanceAction = namedtuple("UpdateAppearanceAction", "name action_name values")
FeedbackAction = namedtuple("FeedbackAction", "name action_name values")
##############################################################################################################################################


# 场景可以用的所有动作
STAGE_AVAILABLE_ACTIONS_REGISTER = [
    #AttackAction,
    TagAction,
    MindVoiceAction,
    WhisperAction,
    StageNarrateAction,
    FeedbackAction,
]

# 角色可以用的所有动作
ACTOR_AVAILABLE_ACTIONS_REGISTER = [
    #AttackAction,
    GoToAction,
    SpeakAction,
    TagAction,
    MindVoiceAction,
    BroadcastAction,
    WhisperAction,
    SearchPropAction,
    PerceptionAction,
    StealPropAction,
    GivePropAction,
    CheckStatusAction,
    UsePropAction,
    BehaviorAction,
    TargetAction,
    SkillAction,
    PropAction,
    UpdateAppearanceAction,
    FeedbackAction,
]

# 角色交互类动作
ACTOR_INTERACTIVE_ACTIONS_REGISTER = [
    SearchPropAction,
    GoToAction,
    PerceptionAction,
    StealPropAction,
    GivePropAction,
    CheckStatusAction,
    UsePropAction,
    BehaviorAction,
    TargetAction,
    SkillAction,
    PropAction,
    UpdateAppearanceAction,
    FeedbackAction,
]
