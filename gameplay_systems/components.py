from collections import namedtuple

############################################# 核心组件（相对通用的？） ############################################################################
# 全局唯一标识符
GUIDComponent = namedtuple("GUIDComponent", "name GUID")
# 管理员标记，世界级别的AI
WorldComponent = namedtuple("WorldComponent", "name")
# 场景标记
StageComponent = namedtuple("StageComponent", "name")
StageArchiveComponent = namedtuple("StageArchiveComponent", "name narrate round")
StageGraphComponent = namedtuple("StageGraphComponent", "name stage_graph")
# 角色标记
ActorComponent = namedtuple("ActorComponent", "name current_stage")
# 玩家标记
PlayerComponent = namedtuple("PlayerComponent", "name")
# 玩家标记: 是网页登陆的客户端
PlayerIsWebClientComponent = namedtuple("PlayerIsWebClientComponent", "name")
# 玩家标记: 是网页登陆的客户端
PlayerIsTerminalClientComponent = namedtuple("PlayerIsTerminalClientComponent", "name")
# 摧毁Entity标记
DestroyComponent = namedtuple("DestroyComponent", "name")
# 自动规划行为的标记
AutoPlanningComponent = namedtuple("AutoPlanningComponent", "name")
# 角色外观信息
AppearanceComponent = namedtuple("AppearanceComponent", "name appearance hash_code")
# 裸身信息，用于和衣服组成完整的外观信息。如果是动物等，就是动物的外观信息
BodyComponent = namedtuple("BodyComponent", "name body")


##############################################################################################################################################

######################################### 测试组件（业务强相关）：RPG Game #######################################################################
RPGAttributesComponent = namedtuple(
    "RPGAttributesComponent", "name maxhp hp attack defense"
)
RPGCurrentWeaponComponent = namedtuple("RPGCurrentWeaponComponent", "name propname")
RPGCurrentClothesComponent = namedtuple("RPGCurrentClothesComponent", "name propname")
##############################################################################################################################################
