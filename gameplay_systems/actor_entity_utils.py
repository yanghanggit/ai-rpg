from entitas import Entity  # type: ignore
from game.rpg_game_context import RPGGameContext
from components.components import (
    AttributesComponent,
    ClothesComponent,
    WeaponComponent,
    FinalAppearanceComponent,
    ActorComponent,
)
from typing import List, Dict, Optional
from extended_systems.prop_file import PropFile
import gameplay_systems.file_system_utils
from models.file_models import PropType


# 简单方便的一次性获取需要的信息。这个类是一个工具类。
class ActorStatusEvaluator:

    def __init__(self, context: RPGGameContext, actor_entity: Entity) -> None:

        assert actor_entity.has(ActorComponent)

        self._name = actor_entity.get(ActorComponent).name
        self._max_hp: int = 0
        self._cur_hp: int = 0
        self._category_prop_files: Dict[str, List[PropFile]] = {}
        self._current_weapon: Optional[PropFile] = None
        self._current_clothes: Optional[PropFile] = None
        self._stage_name: str = ""
        self._appearance: str = ""

        self._validate_state(context, actor_entity)

    ######################################################################################################################################
    @property
    def actor_name(self) -> str:
        return self._name

    ######################################################################################################################################
    @property
    def health_ratio(self) -> float:
        return self._cur_hp / self._max_hp

    ######################################################################################################################################
    @property
    def format_health_info(self) -> str:
        return f"{self._cur_hp}/{self._max_hp}"

    ######################################################################################################################################
    @property
    def stage_name(self) -> str:
        return self._stage_name

    ######################################################################################################################################
    @property
    def appearance(self) -> str:
        return self._appearance

    ######################################################################################################################################
    def _validate_state(self, context: RPGGameContext, actor_entity: Entity) -> None:
        # 检查场景信息
        self._retrieve_stage_name(context, actor_entity)
        # 检查道具信息
        self._retrieve_category_files(context, actor_entity)
        # 检查生命值信息
        self._validate_health(actor_entity)
        # 检查装备信息
        self._validate_equipment(context, actor_entity)
        # 检查外观信息
        assert actor_entity.has(FinalAppearanceComponent)
        self._appearance = str(
            actor_entity.get(FinalAppearanceComponent).final_appearance
        )

    ######################################################################################################################################
    def _retrieve_stage_name(
        self, context: RPGGameContext, actor_entity: Entity
    ) -> None:
        # 害怕，就拷贝了。
        self._stage_name = actor_entity.get(ActorComponent).current_stage

    ######################################################################################################################################
    def _retrieve_category_files(
        self, context: RPGGameContext, actor_entity: Entity
    ) -> None:
        safe_name = context.safe_get_entity_name(actor_entity)
        self._category_prop_files = (
            gameplay_systems.file_system_utils.categorize_files_by_type(
                context.file_system, safe_name
            )
        )

    ######################################################################################################################################
    def _validate_health(self, actor_entity: Entity) -> None:
        if not actor_entity.has(AttributesComponent):
            return
        rpg_attr_comp = actor_entity.get(AttributesComponent)
        self._max_hp = rpg_attr_comp.max_hp
        self._cur_hp = rpg_attr_comp.cur_hp

    ######################################################################################################################################
    def _validate_equipment(
        self, context: RPGGameContext, actor_entity: Entity
    ) -> None:
        safe_name = context.safe_get_entity_name(actor_entity)

        if actor_entity.has(WeaponComponent):
            self._current_weapon = context.file_system.get_file(
                PropFile, safe_name, actor_entity.get(WeaponComponent).prop_name
            )

        if actor_entity.has(ClothesComponent):
            self._current_clothes = context.file_system.get_file(
                PropFile, safe_name, actor_entity.get(ClothesComponent).prop_name
            )

    ######################################################################################################################################
    def _get_category_prop_files(self, prop_type: PropType) -> List[PropFile]:
        return self._category_prop_files.get(prop_type, [])

    ######################################################################################################################################
    @property
    def skill_prop_files(self) -> List[PropFile]:
        return self._get_category_prop_files(PropType.TYPE_SKILL)

    ######################################################################################################################################
    @property
    def available_skill_accessory_prop_files(self) -> List[PropFile]:
        return (
            self._get_category_prop_files(PropType.TYPE_SPECIAL)
            + self._get_category_prop_files(PropType.TYPE_NON_CONSUMABLE_ITEM)
            + self._get_category_prop_files(PropType.TYPE_CONSUMABLE_ITEM)
            + self._get_category_prop_files(PropType.TYPE_WEAPON)
            + self._get_category_prop_files(PropType.TYPE_CLOTHES)
        )

    ######################################################################################################################################
    @property
    def available_stage_condition_prop_files(self) -> List[PropFile]:

        return (
            self._get_category_prop_files(PropType.TYPE_SPECIAL)
            + self._get_category_prop_files(PropType.TYPE_CLOTHES)
            + self._get_category_prop_files(PropType.TYPE_NON_CONSUMABLE_ITEM)
        )

    ######################################################################################################################################
    @property
    def inspectable_prop_files(self) -> List[PropFile]:
        # 只能发现 不可消耗道具。
        return (
            # self._get_category_prop_files(PropType.TYPE_WEAPON)
            # + self._get_category_prop_files(PropType.TYPE_CLOTHES)
            self._get_category_prop_files(PropType.TYPE_NON_CONSUMABLE_ITEM)
            # + self._get_category_prop_files(PropType.TYPE_CONSUMABLE_ITEM)
        )

    ######################################################################################################################################
