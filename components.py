
from collections import namedtuple

###核心组件
WorldComponent = namedtuple('WorldComponent', 'name agent')
StageComponent = namedtuple('StageComponent', 'name agent directorscripts')
NPCComponent = namedtuple('NPCComponent', 'name agent current_stage')
PlayerComponent = namedtuple('PlayerComponent', 'name')
UniquePropComponent = namedtuple('UniquePropComponent', 'name owner')
BagComponent = namedtuple('BagComponent', 'name_items')
###############################################################################################################################################
DestroyComponent = namedtuple('DestroyComponent', 'name')
###############################################################################################################################################
###动作类的组件
RememberActionComponent = namedtuple('RememberActionComponent', 'action')
MindVoiceActionComponent = namedtuple('MindVoiceActionComponent', 'action')
BroadcastActionComponent = namedtuple('BroadcastActionComponent', 'action')
WhisperActionComponent = namedtuple('WhisperActionComponent', 'action')
SpeakActionComponent = namedtuple('SpeakActionComponent', 'action')
FightActionComponent = namedtuple('FightActionComponent', 'action')
LeaveActionComponent = namedtuple('LeaveActionComponent', 'action')
TagActionComponent = namedtuple('TagActionComponent', 'action')
DeadActionComponent = namedtuple('DeadActionComponent', 'action')
SearchActionComponent = namedtuple('SearchActionComponent', 'action')
###############################################################################################################################################
###游戏业务组件
SimpleRPGRoleComponent = namedtuple('SimpleRPGRoleComponent', 'name maxhp hp attack desc')
###############################################################################################################################################
###特殊标记类
HumanInterferenceComponent = namedtuple('HumanInterferenceComponent', 'reason')