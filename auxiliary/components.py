
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
PerceptionActionComponent = namedtuple('PerceptionActionComponent', 'action')
StealActionComponent = namedtuple('StealActionComponent', 'action')
TradeActionComponent = namedtuple('TradeActionComponent', 'action')
CheckStatusActionComponent = namedtuple('CheckStatusActionComponent', 'action')
###############################################################################################################################################
###游戏业务组件
SimpleRPGRoleComponent = namedtuple('SimpleRPGRoleComponent', 'name maxhp hp attack')
###############################################################################################################################################


#注册一下方便使用
STAGE_AVAILABLE_ACTIONS_REGISTER = [ FightActionComponent, 
                            SpeakActionComponent, 
                            TagActionComponent, 
                            RememberActionComponent,
                            MindVoiceActionComponent,
                            BroadcastActionComponent,
                            WhisperActionComponent]

STAGE_DIALOGUE_ACTIONS_REGISTER = [SpeakActionComponent, MindVoiceActionComponent, WhisperActionComponent]


#注册一下方便使用
NPC_AVAILABLE_ACTIONS_REGISTER = [FightActionComponent, 
                         LeaveForActionComponent, 
                         SpeakActionComponent, 
                         TagActionComponent, 
                         RememberActionComponent, 
                         MindVoiceActionComponent, 
                         BroadcastActionComponent,
                         WhisperActionComponent,
                         SearchActionComponent, 
                         PrisonBreakActionComponent,
                         PerceptionActionComponent,
                         StealActionComponent,
                         TradeActionComponent,
                         CheckStatusActionComponent]

NPC_DIALOGUE_ACTIONS_REGISTER = [SpeakActionComponent, MindVoiceActionComponent, WhisperActionComponent]
NPC_INTERACTIVE_ACTIONS_REGISTER = [SearchActionComponent, 
                                    LeaveForActionComponent, 
                                    PrisonBreakActionComponent, 
                                    PerceptionActionComponent,
                                    StealActionComponent,
                                    TradeActionComponent,
                                    CheckStatusActionComponent]