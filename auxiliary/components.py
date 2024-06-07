from collections import namedtuple

############################################# 核心组件（相对通用的？） ############################################################################
# 管理员标记，世界级别的AI
WorldComponent = namedtuple('WorldComponent', 'name')
# 场景标记
StageComponent = namedtuple('StageComponent', 'name')
# 角色标记
ActorComponent = namedtuple('ActorComponent', 'name current_stage')
# 玩家标记
PlayerComponent = namedtuple('PlayerComponent', 'name')
# 摧毁Entity标记
DestroyComponent = namedtuple('DestroyComponent', 'name')
# 自动规划行为的标记
AutoPlanningComponent = namedtuple('AutoPlanningComponent', 'name')
# 外形信息
AppearanceComponent = namedtuple('AppearanceComponent', 'appearance')
# 场景离开条件
StageExitCondStatusComponent = namedtuple('StageExitCondStatusComponent', 'condition')
StageExitCondCheckRoleStatusComponent = namedtuple('StageExitCondCheckRoleStatusComponent', 'condition')
StageExitCondCheckRolePropsComponent = namedtuple('StageExitCondCheckRolePropsComponent', 'condition')
# 场景进入条件
StageEntryCondStatusComponent = namedtuple('StageEntryCondStatusComponent', 'condition')
StageEntryCondCheckRoleStatusComponent = namedtuple('StageEntryCondCheckRoleStatusComponent', 'condition')
StageEntryCondCheckRolePropsComponent = namedtuple('StageEntryCondCheckRolePropsComponent', 'condition')
# 作为门类型的场景的组件标记
ExitOfPortalComponent = namedtuple('ExitOfPortalComponent', 'name')
##############################################################################################################################################


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
SearchActionComponent = namedtuple('SearchActionComponent', 'action')
# 从目标角色处偷取
StealActionComponent = namedtuple('StealActionComponent', 'action')
# 将道具交给目标角色
TradeActionComponent = namedtuple('TradeActionComponent', 'action')
# 使用道具
UsePropActionComponent = namedtuple('UsePropActionComponent', 'action')
# 感知场景内的信息（角色与道具）
PerceptionActionComponent = namedtuple('PerceptionActionComponent', 'action')
# 检查自身状态
CheckStatusActionComponent = namedtuple('CheckStatusActionComponent', 'action')
##############################################################################################################################################

######################################### 测试组件（业务强相关）：RPG Game #######################################################################
SimpleRPGRoleComponent = namedtuple('SimpleRPGRoleComponent', 'name maxhp hp attack defense')
SimpleRPGRoleWeaponComponent = namedtuple('SimpleRPGRoleWeaponComponent', 'name weaponname maxhp attack defense')
SimpleRPGRoleArmorComponent = namedtuple('SimpleRPGRoleArmorComponent', 'name armorname maxhp attack defense')
##############################################################################################################################################


#场景可以用的所有动作
STAGE_AVAILABLE_ACTIONS_REGISTER = [AttackActionComponent,
                                    TagActionComponent, 
                                    MindVoiceActionComponent,
                                    WhisperActionComponent,
                                    EnviroNarrateActionComponent]

#场景对话类动作
STAGE_DIALOGUE_ACTIONS_REGISTER = [SpeakActionComponent,
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
                         SearchActionComponent, 
                         PortalStepActionComponent,
                         PerceptionActionComponent,
                         StealActionComponent,
                         TradeActionComponent,
                         CheckStatusActionComponent,
                         UsePropActionComponent]

#角色对话类动作
ACTOR_DIALOGUE_ACTIONS_REGISTER = [SpeakActionComponent, 
                                BroadcastActionComponent,
                                WhisperActionComponent]

#角色交互类动作
ACTOR_INTERACTIVE_ACTIONS_REGISTER = [SearchActionComponent, 
                                    GoToActionComponent, 
                                    PortalStepActionComponent, 
                                    PerceptionActionComponent,
                                    StealActionComponent,
                                    TradeActionComponent,
                                    CheckStatusActionComponent,
                                    UsePropActionComponent]