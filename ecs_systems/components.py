from collections import namedtuple

############################################# 核心组件（相对通用的？） ############################################################################
# 全局唯一标识符
GUIDComponent = namedtuple('GUIDComponent', 'GUID')
# 管理员标记，世界级别的AI
WorldComponent = namedtuple('WorldComponent', 'name')
# 场景标记
StageComponent = namedtuple('StageComponent', 'name')
# 角色标记
ActorComponent = namedtuple('ActorComponent', 'name current_stage')
# 玩家标记
PlayerComponent = namedtuple('PlayerComponent', 'name')
# 玩家标记: 是网页登陆的客户端
PlayerIsWebClientComponent = namedtuple('PlayerIsWebClientComponent', 'name')
# 玩家标记: 是网页登陆的客户端
PlayerIsTerminalClientComponent = namedtuple('PlayerIsTerminalClientComponent', 'name')
# 摧毁Entity标记
DestroyComponent = namedtuple('DestroyComponent', 'name')
# 自动规划行为的标记
AutoPlanningComponent = namedtuple('AutoPlanningComponent', 'name')
# 外观信息
AppearanceComponent = namedtuple('AppearanceComponent', 'appearance hash_code')
# 纯粹的身体信息，用于和衣服组成完整的外观信息。如果是动物等，就是动物的外观信息
BodyComponent = namedtuple('BodyComponent', 'body')
# 场景离开条件
StageExitCondStatusComponent = namedtuple('StageExitCondStatusComponent', 'condition')
StageExitCondCheckActorStatusComponent = namedtuple('StageExitCondCheckActorStatusComponent', 'condition')
StageExitCondCheckActorPropsComponent = namedtuple('StageExitCondCheckActorPropsComponent', 'condition')
# 场景进入条件
StageEntryCondStatusComponent = namedtuple('StageEntryCondStatusComponent', 'condition')
StageEntryCondCheckActorStatusComponent = namedtuple('StageEntryCondCheckActorStatusComponent', 'condition')
StageEntryCondCheckActorPropsComponent = namedtuple('StageEntryCondCheckActorPropsComponent', 'condition')
# 作为门类型的场景的组件标记
ExitOfPortalComponent = namedtuple('ExitOfPortalComponent', 'name')
##############################################################################################################################################


#SimpleRPGAttrComponent
######################################### 测试组件（业务强相关）：RPG Game #######################################################################
SimpleRPGAttrComponent = namedtuple('SimpleRPGAttrComponent', 'name maxhp hp attack defense')
SimpleRPGWeaponComponent = namedtuple('SimpleRPGWeaponComponent', 'name weaponname maxhp attack defense')
SimpleRPGArmorComponent = namedtuple('SimpleRPGArmorComponent', 'name armorname maxhp attack defense')
##############################################################################################################################################
