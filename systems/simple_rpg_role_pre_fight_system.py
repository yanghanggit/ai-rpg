from entitas import Matcher, ExecuteProcessor,Entity #type: ignore
from auxiliary.components import SimpleRPGRoleComponent, SimpleRPGRoleWeaponComponent, SimpleRPGRoleArmorComponent, StageComponent
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from typing import Set

# 这是一个测试，将装备对战斗数值的影响先做一个初步的。
# 后续不能这么写。在战斗前重新构造武器和防具是不合理的
# 按理讲，应该有ChangeEquipmentAction来做更换装备。因为如果身可能有多个武器与防具，但一般只能使用一个。现在是遇到第一个就break了
class SimpleRPGRolePreFightSystem(ExecuteProcessor):
    
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
######################################################################################################################################################
    def execute(self) -> None:
        self.clear_weapons_and_armors()
        self.rebuild_weapons_from_prop_files()
        self.rebuild_armors_from_prop_files()
######################################################################################################################################################
    def clear_weapons_and_armors(self) -> None:
        rpgentities: Set[Entity] = self.context.get_group(Matcher(SimpleRPGRoleComponent)).entities
        for entity in rpgentities:
            
            if entity.has(SimpleRPGRoleWeaponComponent):
                entity.remove(SimpleRPGRoleWeaponComponent)

            if entity.has(SimpleRPGRoleArmorComponent):
                entity.remove(SimpleRPGRoleArmorComponent)
######################################################################################################################################################
    # 临时的方案，最暴力的方式
    def rebuild_weapons_from_prop_files(self) -> None:
        filesystem = self.context.file_system
        rpgentities: Set[Entity] = self.context.get_group(Matcher(SimpleRPGRoleComponent)).entities
        for entity in rpgentities:
            if entity.has(StageComponent):
                continue
            safename = self.context.safe_get_entity_name(entity)            
            files = filesystem.get_prop_files(safename)
            for _file in files:
                if _file.prop.is_weapon():
                    entity.add(SimpleRPGRoleWeaponComponent, safename, _file.prop.name, _file.prop.maxhp, _file.prop.attack, _file.prop.defense)
                    logger.info(f"SimpleRPGRolePreFightSystem: {safename} add weapon {_file.prop.name}")
                    break # 遇到第一个武器就break，这是不合理的，后续需要改进
######################################################################################################################################################
    def rebuild_armors_from_prop_files(self) -> None:
        filesystem = self.context.file_system
        rpgentities: Set[Entity] = self.context.get_group(Matcher(SimpleRPGRoleComponent)).entities
        for entity in rpgentities:
            if entity.has(StageComponent):
                continue
            safename = self.context.safe_get_entity_name(entity)            
            files = filesystem.get_prop_files(safename)
            for _file in files:
                if _file.prop.is_clothes():
                    entity.add(SimpleRPGRoleArmorComponent, safename,  _file.prop.name, _file.prop.maxhp, _file.prop.attack, _file.prop.defense)
                    logger.info(f"SimpleRPGRolePreFightSystem: {safename} add armor {_file.prop.name}")
                    break # 遇到第一个防具就break，这是不合理的，后续需要改进
######################################################################################################################################################