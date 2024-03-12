
from collections import namedtuple

#类型标记类
WorldComponent = namedtuple('WorldComponent', 'name agent')
StageComponent = namedtuple('StageComponent', 'name agent events')
NPCComponent = namedtuple('NPCComponent', 'name agent current_stage')
PlayerComponent = namedtuple('PlayerComponent', 'name')
###############################################################################################################################################
DestroyComponent = namedtuple('DestroyComponent', 'cause')
###############################################################################################################################################
###动作类的组件
SpeakActionComponent = namedtuple('SpeakActionComponent', 'action')
FightActionComponent = namedtuple('FightActionComponent', 'action')
LeaveActionComponent = namedtuple('LeaveActionComponent', 'action')
DeadActionComponent = namedtuple('DeadActionComponent', 'cause')
TagActionComponent = namedtuple('TagActionComponent', 'cause')
###############################################################################################################################################
