
from collections import namedtuple

###核心组件
###############################################################################################################################################
WorldComponent = namedtuple('WorldComponent', 'name')
StageComponent = namedtuple('StageComponent', 'name')
ConnectToStageComponent = namedtuple('ConnectToStageComponent', 'name')
NPCComponent = namedtuple('NPCComponent', 'name current_stage')
PlayerComponent = namedtuple('PlayerComponent', 'name')
StageEntryConditionComponent = namedtuple('StageEntryConditionComponent', 'conditions')
StageExitConditionComponent = namedtuple('StageExitConditionComponent', 'conditions')
DestroyComponent = namedtuple('DestroyComponent', 'name')
AutoPlanningComponent = namedtuple('AutoPlanningComponent', 'name')
###############################################################################################################################################
###动作类的组件
RememberActionComponent = namedtuple('RememberActionComponent', 'action')
MindVoiceActionComponent = namedtuple('MindVoiceActionComponent', 'action')
BroadcastActionComponent = namedtuple('BroadcastActionComponent', 'action')
WhisperActionComponent = namedtuple('WhisperActionComponent', 'action')
SpeakActionComponent = namedtuple('SpeakActionComponent', 'action')
FightActionComponent = namedtuple('FightActionComponent', 'action')
LeaveForActionComponent = namedtuple('LeaveForActionComponent', 'action')
TagActionComponent = namedtuple('TagActionComponent', 'action')
DeadActionComponent = namedtuple('DeadActionComponent', 'action')
SearchActionComponent = namedtuple('SearchActionComponent', 'action')
PrisonBreakActionComponent = namedtuple('PrisonBreakActionComponent', 'action')
###############################################################################################################################################
###游戏业务组件
SimpleRPGRoleComponent = namedtuple('SimpleRPGRoleComponent', 'name maxhp hp attack')
###############################################################################################################################################


#注册一下方便使用
stage_available_actions_register = [ FightActionComponent, 
                            SpeakActionComponent, 
                            TagActionComponent, 
                            RememberActionComponent,
                            MindVoiceActionComponent,
                            BroadcastActionComponent,
                            WhisperActionComponent]

stage_dialogue_actions_register = [SpeakActionComponent, MindVoiceActionComponent, WhisperActionComponent]


#注册一下方便使用
npc_available_actions_register = [FightActionComponent, 
                         LeaveForActionComponent, 
                         SpeakActionComponent, 
                         TagActionComponent, 
                         RememberActionComponent, 
                         MindVoiceActionComponent, 
                         BroadcastActionComponent,
                         WhisperActionComponent,
                         SearchActionComponent, 
                         PrisonBreakActionComponent]

npc_dialogue_actions_register = [SpeakActionComponent, MindVoiceActionComponent, WhisperActionComponent]
npc_interactive_actions_register = [SearchActionComponent, LeaveForActionComponent, PrisonBreakActionComponent]