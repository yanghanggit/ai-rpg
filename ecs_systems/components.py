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
# 角色外观信息
AppearanceComponent = namedtuple('AppearanceComponent', 'name appearance hash_code')
# 裸身信息，用于和衣服组成完整的外观信息。如果是动物等，就是动物的外观信息
BodyComponent = namedtuple('BodyComponent', 'name body')
# 场景离开条件
StageExitCondStatusComponent = namedtuple('StageExitCondStatusComponent', 'name condition')
StageExitCondCheckActorStatusComponent = namedtuple('StageExitCondCheckActorStatusComponent', 'name condition')
StageExitCondCheckActorPropsComponent = namedtuple('StageExitCondCheckActorPropsComponent', 'name condition')
# 场景进入条件
StageEntryCondStatusComponent = namedtuple('StageEntryCondStatusComponent', 'name condition')
StageEntryCondCheckActorStatusComponent = namedtuple('StageEntryCondCheckActorStatusComponent', 'name condition')
StageEntryCondCheckActorPropsComponent = namedtuple('StageEntryCondCheckActorPropsComponent', 'name condition')
# 作为门类型的场景的组件标记
StagePortalComponent = namedtuple('StagePortalComponent', 'name target')  #StagePortalComponent
##############################################################################################################################################


#SimpleRPGAttrComponent
######################################### 测试组件（业务强相关）：RPG Game #######################################################################
SimpleRPGAttrComponent = namedtuple('SimpleRPGAttrComponent', 'name maxhp hp attack defense')
SimpleRPGWeaponComponent = namedtuple('SimpleRPGWeaponComponent', 'name weaponname maxhp attack defense')
SimpleRPGArmorComponent = namedtuple('SimpleRPGArmorComponent', 'name armorname maxhp attack defense')
##############################################################################################################################################

# 角色当前装备的道具，一般是武器和衣服
CurrentUsingPropComponent = namedtuple('CurrentUsingPropComponent', 'name weapon clothes')
