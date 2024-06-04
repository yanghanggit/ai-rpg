from collections import namedtuple

###核心组件
###############################################################################################################################################
WorldComponent = namedtuple('WorldComponent', 'name')
StageComponent = namedtuple('StageComponent', 'name')
ExitOfPortalComponent = namedtuple('ExitOfPortalComponent', 'name')
NPCComponent = namedtuple('NPCComponent', 'name current_stage')
PlayerComponent = namedtuple('PlayerComponent', 'name')
# StageEntryConditionComponent = namedtuple('StageEntryConditionComponent', 'conditions')
# StageExitConditionComponent = namedtuple('StageExitConditionComponent', 'conditions')
DestroyComponent = namedtuple('DestroyComponent', 'name')
AutoPlanningComponent = namedtuple('AutoPlanningComponent', 'name')
InteractivePropActionComponent = namedtuple('InteractivePropActionComponent', 'interactive_props')
RoleAppearanceComponent = namedtuple('RoleAppearanceComponent', 'appearance')
###############################################################################################################################################
###动作类的组件
MindVoiceActionComponent = namedtuple('MindVoiceActionComponent', 'action')
BroadcastActionComponent = namedtuple('BroadcastActionComponent', 'action')
WhisperActionComponent = namedtuple('WhisperActionComponent', 'action')
SpeakActionComponent = namedtuple('SpeakActionComponent', 'action')
AttackActionComponent = namedtuple('AttackActionComponent', 'action')
LeaveForActionComponent = namedtuple('LeaveForActionComponent', 'action')
TagActionComponent = namedtuple('TagActionComponent', 'action')
DeadActionComponent = namedtuple('DeadActionComponent', 'action')
SearchActionComponent = namedtuple('SearchActionComponent', 'action')
PortalStepActionComponent = namedtuple('PortalStepActionComponent', 'action')
PerceptionActionComponent = namedtuple('PerceptionActionComponent', 'action')
StealActionComponent = namedtuple('StealActionComponent', 'action')
TradeActionComponent = namedtuple('TradeActionComponent', 'action')
CheckStatusActionComponent = namedtuple('CheckStatusActionComponent', 'action')
EnviroNarrateActionComponent = namedtuple('EnviroNarrateActionComponent', 'action')
UseInteractivePropActionComponent = namedtuple('UseInteractivePropActionComponent', 'action')
###############################################################################################################################################
###游戏业务组件
SimpleRPGRoleComponent = namedtuple('SimpleRPGRoleComponent', 'name maxhp hp attack defense')
SimpleRPGRoleWeaponComponent = namedtuple('SimpleRPGRoleWeaponComponent', 'name weaponname maxhp attack defense')
SimpleRPGRoleArmorComponent = namedtuple('SimpleRPGRoleArmorComponent', 'name armorname maxhp attack defense')
###############################################################################################################################################


#注册一下方便使用
STAGE_AVAILABLE_ACTIONS_REGISTER = [AttackActionComponent,
                                    TagActionComponent, 
                                    MindVoiceActionComponent,
                                    WhisperActionComponent,
                                    EnviroNarrateActionComponent]

STAGE_DIALOGUE_ACTIONS_REGISTER = [SpeakActionComponent,
                                MindVoiceActionComponent,
                                WhisperActionComponent]


#注册一下方便使用
NPC_AVAILABLE_ACTIONS_REGISTER = [AttackActionComponent, 
                         LeaveForActionComponent, 
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
                         UseInteractivePropActionComponent]

NPC_DIALOGUE_ACTIONS_REGISTER = [SpeakActionComponent, 
                                BroadcastActionComponent,
                                WhisperActionComponent]

NPC_INTERACTIVE_ACTIONS_REGISTER = [SearchActionComponent, 
                                    LeaveForActionComponent, 
                                    PortalStepActionComponent, 
                                    PerceptionActionComponent,
                                    StealActionComponent,
                                    TradeActionComponent,
                                    CheckStatusActionComponent,
                                    UseInteractivePropActionComponent]

# todo 离开条件
StageExitCondStatusComponent = namedtuple('StageExitCondStatusComponent', 'condition')
StageExitCondCheckRoleStatusComponent = namedtuple('StageExitCondCheckRoleStatusComponent', 'condition')
StageExitCondCheckRolePropsComponent = namedtuple('StageExitCondCheckRolePropsComponent', 'condition')
# todo 进入条件
StageEntryCondStatusComponent = namedtuple('StageEntryCondStatusComponent', 'condition')
StageEntryCondCheckRoleStatusComponent = namedtuple('StageEntryCondCheckRoleStatusComponent', 'condition')
StageEntryCondCheckRolePropsComponent = namedtuple('StageEntryCondCheckRolePropsComponent', 'condition')