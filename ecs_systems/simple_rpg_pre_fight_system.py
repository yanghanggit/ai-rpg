# from entitas import Matcher, ExecuteProcessor, Entity  # type: ignore
# from ecs_systems.components import (
#     RPGAttributesComponent,
#     RPGCurrentWeaponComponent,
#     RPGCurrentClothesComponent,
#     StageComponent,
# )
# from rpg_game.rpg_entitas_context import RPGEntitasContext
# from typing import Set, Optional, override
# from file_system.files_def import PropFile


# # 这是一个测试，将装备对战斗数值的影响先做一个初步的。
# # 后续不能这么写。在战斗前重新构造武器和防具是不合理的
# # 按理讲，应该有ChangeEquipmentAction来做更换装备。因为如果身可能有多个武器与防具，但一般只能使用一个。现在是遇到第一个就break了
# class SimpleRPGPreFightSystem(ExecuteProcessor):

#     def __init__(self, context: RPGEntitasContext) -> None:
#         self._context: RPGEntitasContext = context

#     ######################################################################################################################################################
#     @override
#     def execute(self) -> None:
#         self.clear_weapons_and_armors()
#         self.rebuild_weapons_from_prop_files()
#         self.rebuild_armors_from_prop_files()

#     ######################################################################################################################################################
#     def clear_weapons_and_armors(self) -> None:
#         rpgentities: Set[Entity] = self._context.get_group(
#             Matcher(RPGAttributesComponent)
#         ).entities.copy()
#         for entity in rpgentities:

#             if entity.has(RPGCurrentWeaponComponent):
#                 entity.remove(RPGCurrentWeaponComponent)

#             if entity.has(RPGCurrentClothesComponent):
#                 entity.remove(RPGCurrentClothesComponent)

#     ######################################################################################################################################################
#     # 临时的方案，最暴力的方式
#     def rebuild_weapons_from_prop_files(self) -> None:
#         rpgentities: Set[Entity] = self._context.get_group(
#             Matcher(RPGAttributesComponent)
#         ).entities
#         for entity in rpgentities:
#             if entity.has(StageComponent):
#                 continue
#             highest_attack_weapon = self.get_weapon_with_highest_attack_power(entity)
#             if highest_attack_weapon is not None:

#                 entity.add(
#                     RPGCurrentWeaponComponent,
#                     self._context.safe_get_entity_name(entity),
#                     highest_attack_weapon.name,
#                     highest_attack_weapon.max_hp,
#                     highest_attack_weapon.attack,
#                     highest_attack_weapon.defense,
#                 )
#                 continue

#     ######################################################################################################################################################
#     def rebuild_armors_from_prop_files(self) -> None:
#         rpgentities: Set[Entity] = self._context.get_group(
#             Matcher(RPGAttributesComponent)
#         ).entities
#         for entity in rpgentities:
#             if entity.has(StageComponent):
#                 continue
#             highest_defense_armor = self.get_armor_with_highest_defense_power(entity)
#             if highest_defense_armor is not None:
#                 entity.add(
#                     RPGCurrentClothesComponent,
#                     self._context.safe_get_entity_name(entity),
#                     highest_defense_armor.name,
#                     highest_defense_armor.max_hp,
#                     highest_defense_armor.attack,
#                     highest_defense_armor.defense,
#                 )
#                 continue

#     ######################################################################################################################################################
#     def get_weapon_with_highest_attack_power(
#         self, entity: Entity
#     ) -> Optional[PropFile]:
#         safe_name = self._context.safe_get_entity_name(entity)
#         prop_files = self._context._file_system.get_files(PropFile, safe_name)
#         #
#         highest_attack = 0
#         highest_attack_weapon = None
#         for prop_file in prop_files:
#             if prop_file.is_weapon and prop_file.attack > highest_attack:
#                 highest_attack = prop_file.attack
#                 highest_attack_weapon = prop_file

#         return highest_attack_weapon

#     ######################################################################################################################################################
#     def get_armor_with_highest_defense_power(
#         self, entity: Entity
#     ) -> Optional[PropFile]:
#         safe_name = self._context.safe_get_entity_name(entity)
#         prop_files = self._context._file_system.get_files(PropFile, safe_name)
#         #
#         highest_defense = 0
#         highest_defense_armor = None
#         for prop_file in prop_files:
#             if prop_file.is_clothes and prop_file.defense > highest_defense:
#                 highest_defense = prop_file.defense
#                 highest_defense_armor = prop_file
#         return highest_defense_armor


# ######################################################################################################################################################
