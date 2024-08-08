from collections import namedtuple


################################################ 动作组件： ####################################################################################
# 场景环境的描述
EnviroNarrateActionComponent = namedtuple('EnviroNarrateActionComponent', 'action')
# 内心独白
MindVoiceActionComponent = namedtuple('MindVoiceActionComponent', 'action')
# 场景内广播
BroadcastActionComponent = namedtuple('BroadcastActionComponent', 'action')
# 私下交流
WhisperActionComponent = namedtuple('WhisperActionComponent', 'action')
# 对谁说（场景内其他角色能听到）
SpeakActionComponent = namedtuple('SpeakActionComponent', 'action')
# 标签
TagActionComponent = namedtuple('TagActionComponent', 'action')
# 攻击
AttackActionComponent = namedtuple('AttackActionComponent', 'action')
# 死亡
DeadActionComponent = namedtuple('DeadActionComponent', 'action')
# 离开当前场景并去往
GoToActionComponent = namedtuple('GoToActionComponent', 'action')
# 当前场景为‘门’，通过门进入下一个场景
PortalStepActionComponent = namedtuple('PortalStepActionComponent', 'action')
# 寻找场景内道具
SearchPropActionComponent = namedtuple('SearchPropActionComponent', 'action')
# 从目标角色处偷取
StealPropActionComponent = namedtuple('StealPropActionComponent', 'action')
# 将道具交给目标角色
GivePropActionComponent = namedtuple('GivePropActionComponent', 'action')
# 使用道具
UsePropActionComponent = namedtuple('UsePropActionComponent', 'action')
# 感知场景内的信息（角色与道具）
PerceptionActionComponent = namedtuple('PerceptionActionComponent', 'action')
# 检查自身状态
CheckStatusActionComponent = namedtuple('CheckStatusActionComponent', 'action')
##############################################################################################################################################



#场景可以用的所有动作
STAGE_AVAILABLE_ACTIONS_REGISTER = [AttackActionComponent,
                                    TagActionComponent, 
                                    MindVoiceActionComponent,
                                    WhisperActionComponent,
                                    EnviroNarrateActionComponent]

#场景对话类动作
STAGE_CONVERSATION_ACTIONS_REGISTER = [SpeakActionComponent,
                                MindVoiceActionComponent,
                                WhisperActionComponent]


#角色可以用的所有动作
ACTOR_AVAILABLE_ACTIONS_REGISTER = [AttackActionComponent, 
                         GoToActionComponent, 
                         SpeakActionComponent, 
                         TagActionComponent, 
                         MindVoiceActionComponent, 
                         BroadcastActionComponent,
                         WhisperActionComponent,
                         SearchPropActionComponent, 
                         PortalStepActionComponent,
                         PerceptionActionComponent,
                         StealPropActionComponent,
                         GivePropActionComponent,
                         CheckStatusActionComponent,
                         UsePropActionComponent]

#角色对话类动作
ACTOR_CONVERSATION_ACTIONS_REGISTER = [SpeakActionComponent, 
                                BroadcastActionComponent,
                                WhisperActionComponent]

#角色交互类动作
ACTOR_INTERACTIVE_ACTIONS_REGISTER = [SearchPropActionComponent, 
                                    GoToActionComponent, 
                                    PortalStepActionComponent, 
                                    PerceptionActionComponent,
                                    StealPropActionComponent,
                                    GivePropActionComponent,
                                    CheckStatusActionComponent,
                                    UsePropActionComponent]