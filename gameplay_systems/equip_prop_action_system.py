from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_components.action_components import (
    EquipPropAction,
    DeadAction,
    UpdateAppearanceAction,
)
from my_components.components import (
    ActorComponent,
    WeaponComponent,
    ClothesComponent,
)
from loguru import logger
from typing import final, override
from extended_systems.prop_file import PropFile
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent


################################################################################################################################################
def _generate_equipment_not_found_prompt(actor_name: str, prop_name: str) -> str:
    return f"""# 提示: {actor_name} 没有道具: {prop_name}。所以无法装备。"""


################################################################################################################################################
def _generate_equipment_weapon_prompt(
    actor_name: str, prop_file_weapon: PropFile
) -> str:
    assert prop_file_weapon.is_weapon
    return f"""# 发生事件: {actor_name} 装备了武器: {prop_file_weapon.name} """


################################################################################################################################################
def _generate_equipment_clothing_prompt(
    actor_name: str, prop_file_clothes: PropFile
) -> str:
    assert prop_file_clothes.is_clothes
    return f"""# # 发生事件: {actor_name} 装备了衣服: {prop_file_clothes.name} """


################################################################################################################################################
def _generate_equipment_repeat_prompt(actor_name: str, prop_file: PropFile) -> str:
    return f"""# 提示: {actor_name} 已经装备了{prop_file.name}。
无需使用动作:{EquipPropAction.__name__}，重复装备！"""


################################################################################################################################################
################################################################################################################################################
################################################################################################################################################


@final
class EquipPropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(EquipPropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(EquipPropAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_equipment_action(entity)

    ####################################################################################################################################
    def _process_equipment_action(self, entity: Entity) -> None:

        equip_prop_action = entity.get(EquipPropAction)
        if len(equip_prop_action.values) == 0:
            return

        actor_name = self._context.safe_get_entity_name(entity)
        for equip_prop_file_name in equip_prop_action.values:

            prop_file = self._context.file_system.get_file(
                PropFile, actor_name, equip_prop_file_name
            )

            if prop_file is None:
                logger.error(
                    f"EquipPropActionSystem: {actor_name} can't find prop {equip_prop_file_name}"
                )

                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message=_generate_equipment_not_found_prompt(
                            actor_name, equip_prop_file_name
                        )
                    ),
                )
                continue

            if prop_file.is_weapon:
                self._apply_weapon_equipment(entity, prop_file)

            elif prop_file.is_clothes:
                if self._apply_clothing_equipment(entity, prop_file):
                    self._add_update_appearance_action(entity)
            else:
                logger.error(
                    f"EquipPropActionSystem: {actor_name} can't equip prop {equip_prop_file_name}"
                )

    ####################################################################################################################################
    def _apply_weapon_equipment(self, entity: Entity, prop_file: PropFile) -> bool:

        assert prop_file.is_weapon

        if entity.has(WeaponComponent):
            weapon_component = entity.get(WeaponComponent)
            if weapon_component.propname == prop_file.name:
                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message=_generate_equipment_repeat_prompt(
                            self._context.safe_get_entity_name(entity), prop_file
                        )
                    ),
                )
                return False

        entity.replace(WeaponComponent, prop_file.owner_name, prop_file.name)
        self._context.notify_event(
            set({entity}),
            AgentEvent(
                message=_generate_equipment_weapon_prompt(
                    prop_file.owner_name, prop_file
                )
            ),
        )

        return True

    ####################################################################################################################################
    def _apply_clothing_equipment(self, entity: Entity, prop_file: PropFile) -> bool:

        assert prop_file.is_clothes

        if entity.has(ClothesComponent):
            clothes_component = entity.get(ClothesComponent)
            if clothes_component.propname == prop_file.name:
                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message=_generate_equipment_repeat_prompt(
                            self._context.safe_get_entity_name(entity), prop_file
                        )
                    ),
                )
                return False

        entity.replace(ClothesComponent, prop_file.owner_name, prop_file.name)
        self._context.notify_event(
            set({entity}),
            AgentEvent(
                message=_generate_equipment_clothing_prompt(
                    prop_file.owner_name, prop_file
                )
            ),
        )

        return True

    ####################################################################################################################################
    def _add_update_appearance_action(self, entity: Entity) -> None:
        entity.replace(
            UpdateAppearanceAction,
            self._context.safe_get_entity_name(entity),
            [],
        )

    ####################################################################################################################################
