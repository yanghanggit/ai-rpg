from entitas import Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from gameplay_systems.components import (
    RPGAttributesComponent,
    RPGCurrentClothesComponent,
    RPGCurrentWeaponComponent,
)
from typing import List, Dict, Optional
from file_system.files_def import PropFile
import file_system.helper


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class CheckSelfHelper:

    def __init__(self, context: RPGEntitasContext, entity: Entity) -> None:
        self._maxhp: int = 0
        self._hp: int = 0
        self._categorized_prop_files: Dict[str, List[PropFile]] = {}
        self._current_weapon: Optional[PropFile] = None
        self._current_clothes: Optional[PropFile] = None

        #
        self.check(context, entity)

    def check(self, context: RPGEntitasContext, entity: Entity) -> None:
        self.check_props(context, entity)
        self.check_health(entity)
        self.check_equipment(context, entity)

    def check_props(self, context: RPGEntitasContext, entity: Entity) -> None:
        safe_name = context.safe_get_entity_name(entity)
        self._categorized_prop_files = file_system.helper.get_categorized_files_dict(
            context._file_system, safe_name
        )

    def check_health(self, entity: Entity) -> None:
        if not entity.has(RPGAttributesComponent):
            return
        rpg_attr_comp = entity.get(RPGAttributesComponent)
        self._maxhp = rpg_attr_comp.maxhp
        self._hp = rpg_attr_comp.hp

    def check_equipment(self, context: RPGEntitasContext, entity: Entity) -> None:
        safe_name = context.safe_get_entity_name(entity)

        if entity.has(RPGCurrentWeaponComponent):
            self._current_weapon = context._file_system.get_file(
                PropFile, safe_name, entity.get(RPGCurrentWeaponComponent).propname
            )

        if entity.has(RPGCurrentClothesComponent):
            self._current_clothes = context._file_system.get_file(
                PropFile, safe_name, entity.get(RPGCurrentClothesComponent).propname
            )

    def get_prop_files(self, prop_type: str) -> List[PropFile]:
        return self._categorized_prop_files.get(prop_type, [])

    @property
    def health(self) -> float:
        return self._hp / self._maxhp
