from entitas import Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_components.components import (
    RPGAttributesComponent,
    RPGCurrentClothesComponent,
    RPGCurrentWeaponComponent,
    AppearanceComponent,
)
from typing import List, Dict, Optional
from extended_systems.prop_file import PropFile
import extended_systems.file_system_util
from my_models.file_models import PropType


# 简单方便的一次性获取需要的信息。这个类是一个工具类。
class ActorChecker:

    def __init__(self, context: RPGEntitasContext, entity: Entity) -> None:

        self._maxhp: int = 0
        self._hp: int = 0
        self._category_prop_files: Dict[str, List[PropFile]] = {}
        self._current_weapon: Optional[PropFile] = None
        self._current_clothes: Optional[PropFile] = None
        self._stage_name: str = ""
        self._appearance: str = ""

        # 直接调用_check方法，获取所有需要的信息。
        self._check(context, entity)

    ######################################################################################################################################
    @property
    def health(self) -> float:
        return self._hp / self._maxhp

    ######################################################################################################################################
    @property
    def stage_name(self) -> str:
        return self._stage_name

    ######################################################################################################################################
    @property
    def appearance(self) -> str:
        return self._appearance

    ######################################################################################################################################
    def _check(self, context: RPGEntitasContext, entity: Entity) -> None:
        # 检查场景信息
        self._check_stage(context, entity)
        # 检查道具信息
        self._check_props(context, entity)
        # 检查生命值信息
        self._check_health(entity)
        # 检查装备信息
        self._check_equipments(context, entity)
        # 检查外观信息
        self._check_appearance(context, entity)

    ######################################################################################################################################
    def _check_appearance(self, context: RPGEntitasContext, entity: Entity) -> None:
        if not entity.has(AppearanceComponent):
            return None
        appearance_comp = entity.get(AppearanceComponent)
        # 害怕，就拷贝了。
        self._appearance = str(appearance_comp.appearance)

    ######################################################################################################################################
    def _check_stage(self, context: RPGEntitasContext, entity: Entity) -> None:
        stage_entity = context.safe_get_stage_entity(entity)
        if stage_entity is None:
            return

        # 害怕，就拷贝了。
        self._stage_name = str(context.safe_get_entity_name(stage_entity))

    ######################################################################################################################################
    def _check_props(self, context: RPGEntitasContext, entity: Entity) -> None:
        safe_name = context.safe_get_entity_name(entity)
        self._category_prop_files = (
            extended_systems.file_system_util.get_categorized_files(
                context._file_system, safe_name
            )
        )

    ######################################################################################################################################
    def _check_health(self, entity: Entity) -> None:
        if not entity.has(RPGAttributesComponent):
            return
        rpg_attr_comp = entity.get(RPGAttributesComponent)
        self._maxhp = rpg_attr_comp.maxhp
        self._hp = rpg_attr_comp.hp

    ######################################################################################################################################
    def _check_equipments(self, context: RPGEntitasContext, entity: Entity) -> None:
        safe_name = context.safe_get_entity_name(entity)

        if entity.has(RPGCurrentWeaponComponent):
            self._current_weapon = context._file_system.get_file(
                PropFile, safe_name, entity.get(RPGCurrentWeaponComponent).propname
            )

        if entity.has(RPGCurrentClothesComponent):
            self._current_clothes = context._file_system.get_file(
                PropFile, safe_name, entity.get(RPGCurrentClothesComponent).propname
            )

    ######################################################################################################################################
    def get_prop_files(self, prop_type: PropType) -> List[PropFile]:
        return self._category_prop_files.get(prop_type, [])

    ######################################################################################################################################
