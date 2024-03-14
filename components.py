
from collections import namedtuple

###类型标记类
WorldComponent = namedtuple('WorldComponent', 'name agent')
StageComponent = namedtuple('StageComponent', 'name agent directorscripts')
NPCComponent = namedtuple('NPCComponent', 'name agent current_stage')
PlayerComponent = namedtuple('PlayerComponent', 'name')
###############################################################################################################################################
DestroyComponent = namedtuple('DestroyComponent', 'name')
###############################################################################################################################################
###动作类的组件
SpeakActionComponent = namedtuple('SpeakActionComponent', 'action')
FightActionComponent = namedtuple('FightActionComponent', 'action')
LeaveActionComponent = namedtuple('LeaveActionComponent', 'action')
TagActionComponent = namedtuple('TagActionComponent', 'action')
DeadActionComponent = namedtuple('DeadActionComponent', 'action')
###############################################################################################################################################
SimpleRPGRoleComponent = namedtuple('SimpleRPGComponent', 'name maxhp hp attack desc')
###############################################################################################################################################
###特殊标记类
HumanInterferenceComponent = namedtuple('HumanInterferenceComponent', 'reason')