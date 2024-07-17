from entitas import Matcher, ExecuteProcessor,Entity #type: ignore
from ecs_systems.components import SimpleRPGAttrComponent, SimpleRPGWeaponComponent, SimpleRPGArmorComponent, StageComponent
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from typing import Set, Optional, override
from prototype_data.data_def import PropData

# 这是一个测试，将装备对战斗数值的影响先做一个初步的。
# 后续不能这么写。在战斗前重新构造武器和防具是不合理的
# 按理讲，应该有ChangeEquipmentAction来做更换装备。因为如果身可能有多个武器与防具，但一般只能使用一个。现在是遇到第一个就break了
class SimpleRPGPreFightSystem(ExecuteProcessor):
    
    def __init__(self, context: ExtendedContext) -> None:
        self._context: ExtendedContext = context
######################################################################################################################################################
    @override
    def execute(self) -> None:
        self.clear_weapons_and_armors()
        self.rebuild_weapons_from_prop_files()
        self.rebuild_armors_from_prop_files()
######################################################################################################################################################
    def clear_weapons_and_armors(self) -> None:
        rpgentities: Set[Entity] = self._context.get_group(Matcher(SimpleRPGAttrComponent)).entities
        for entity in rpgentities:
            
            if entity.has(SimpleRPGWeaponComponent):
                entity.remove(SimpleRPGWeaponComponent)

            if entity.has(SimpleRPGArmorComponent):
                entity.remove(SimpleRPGArmorComponent)
######################################################################################################################################################
    # 临时的方案，最暴力的方式
    def rebuild_weapons_from_prop_files(self) -> None:
        filesystem = self._context._file_system
        rpgentities: Set[Entity] = self._context.get_group(Matcher(SimpleRPGAttrComponent)).entities
        for entity in rpgentities:
            if entity.has(StageComponent):
                continue
            highest_attack_weapon = self.get_weapon_with_highest_attack_power(entity)
            if highest_attack_weapon is not None:
                entity.add(SimpleRPGWeaponComponent, self._context.safe_get_entity_name(entity), highest_attack_weapon._name, highest_attack_weapon.maxhp, highest_attack_weapon.attack, highest_attack_weapon.defense)
                continue
######################################################################################################################################################
    def rebuild_armors_from_prop_files(self) -> None:
        rpgentities: Set[Entity] = self._context.get_group(Matcher(SimpleRPGAttrComponent)).entities
        for entity in rpgentities:
            if entity.has(StageComponent):
                continue
            highest_defense_armor = self.get_armor_with_highest_defense_power(entity)
            if highest_defense_armor is not None:
                entity.add(SimpleRPGArmorComponent, self._context.safe_get_entity_name(entity), highest_defense_armor._name, highest_defense_armor.maxhp, highest_defense_armor.attack, highest_defense_armor.defense)
                continue
######################################################################################################################################################
    def get_weapon_with_highest_attack_power(self, entity: Entity) -> Optional[PropData]:
        filesystem = self._context._file_system
        safename = self._context.safe_get_entity_name(entity)            
        files = filesystem.get_prop_files(safename)
        #
        highest_attack = 0
        highest_attack_weapon = None
        for _file in files:
            if _file._prop.is_weapon() and _file._prop.attack > highest_attack:
                highest_attack = _file._prop.attack
                highest_attack_weapon = _file._prop

        return highest_attack_weapon
######################################################################################################################################################
    def get_armor_with_highest_defense_power(self, entity: Entity) -> Optional[PropData]:
        filesystem = self._context._file_system
        safename = self._context.safe_get_entity_name(entity)            
        files = filesystem.get_prop_files(safename)
        #
        highest_defense = 0
        highest_defense_armor = None
        for _file in files:
            if _file._prop.is_clothes() and _file._prop.defense > highest_defense:
                highest_defense = _file._prop.defense
                highest_defense_armor = _file._prop
        return highest_defense_armor
######################################################################################################################################################
        
