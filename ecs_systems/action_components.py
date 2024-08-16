from collections import namedtuple


################################################ 动作组件： ####################################################################################
# 场景环境的描述
StageNarrateAction = namedtuple('StageNarrateAction', 'action')
StageConditionCheckAction = namedtuple('StageConditionCheckAction', 'action')
StageInteractionFeedbackAction = namedtuple('StageInteractionFeedbackAction', 'action')

# 内心独白
MindVoiceAction = namedtuple('MindVoiceAction', 'action')
# 场景内广播
BroadcastAction = namedtuple('BroadcastAction', 'action')
# 私下交流
WhisperAction = namedtuple('WhisperAction', 'action')
# 对谁说（场景内其他角色能听到）
SpeakAction = namedtuple('SpeakAction', 'action')
# 标签
TagAction = namedtuple('TagAction', 'action')
# 攻击
AttackAction = namedtuple('AttackAction', 'action')
# 死亡
DeadAction = namedtuple('DeadAction', 'action')
# 离开当前场景并去往
GoToAction = namedtuple('GoToAction', 'action')
# 寻找场景内道具
SearchPropAction = namedtuple('SearchPropAction', 'action')
# 从目标角色处偷取
StealPropAction = namedtuple('StealPropAction', 'action')
# 将道具交给目标角色
GivePropAction = namedtuple('GivePropAction', 'action')
# 使用道具
UsePropAction = namedtuple('UsePropAction', 'action')
# 感知场景内的信息（角色与道具）
PerceptionAction = namedtuple('PerceptionAction', 'action')
# 检查自身状态
CheckStatusAction = namedtuple('CheckStatusAction', 'action')
##############################################################################################################################################



#场景可以用的所有动作
STAGE_AVAILABLE_ACTIONS_REGISTER = [AttackAction,
                                    TagAction, 
                                    MindVoiceAction,
                                    WhisperAction,
                                    StageNarrateAction,
                                    StageConditionCheckAction,
                                    StageInteractionFeedbackAction]

#场景对话类动作
STAGE_CONVERSATION_ACTIONS_REGISTER = [SpeakAction,
                                MindVoiceAction,
                                WhisperAction]


#角色可以用的所有动作
ACTOR_AVAILABLE_ACTIONS_REGISTER = [AttackAction, 
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
                         UsePropAction]

#角色对话类动作
ACTOR_CONVERSATION_ACTIONS_REGISTER = [SpeakAction, 
                                BroadcastAction,
                                WhisperAction]

#角色交互类动作
ACTOR_INTERACTIVE_ACTIONS_REGISTER = [SearchPropAction, 
                                    GoToAction, 
                                    PerceptionAction,
                                    StealPropAction,
                                    GivePropAction,
                                    CheckStatusAction,
                                    UsePropAction]