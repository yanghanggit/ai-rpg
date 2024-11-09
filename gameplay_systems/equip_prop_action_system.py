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


def _generate_equipment_not_found_prompt(actor_name: str, prop_name: str) -> str:
    return f"""# {actor_name} 没有道具: {prop_name}。所以无法装备。"""


################################################################################################################################################


def _generate_equipment_weapon_prompt(
    actor_name: str, prop_file_weapon: PropFile
) -> str:
    assert prop_file_weapon.is_weapon
    return f"""# {actor_name} 装备了武器: {prop_file_weapon.name} """


################################################################################################################################################


def _generate_equipment_clothing_prompt(
    actor_name: str, prop_file_clothes: PropFile
) -> str:
    assert prop_file_clothes.is_clothes
    return f"""# {actor_name} 装备了衣服: {prop_file_clothes.name} """


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
            self.handle(entity)

    ####################################################################################################################################
    def handle(self, entity: Entity) -> None:

        equip_prop_action = entity.get(EquipPropAction)
        if len(equip_prop_action.values) == 0:
            return

        actor_name = self._context.safe_get_entity_name(entity)
        for prop_name in equip_prop_action.values:

            prop_file = self._context._file_system.get_file(
                PropFile, actor_name, prop_name
            )

            if prop_file is None:
                logger.warning(
                    f"EquipPropActionSystem: {actor_name} can't find prop {prop_name}"
                )

                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message_content=_generate_equipment_not_found_prompt(
                            actor_name, prop_name
                        )
                    ),
                )

                continue

            if prop_file.is_weapon:

                entity.replace(WeaponComponent, equip_prop_action.name, prop_name)

                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message_content=_generate_equipment_weapon_prompt(
                            actor_name, prop_file
                        )
                    ),
                )

            elif prop_file.is_clothes:

                entity.replace(ClothesComponent, equip_prop_action.name, prop_name)

                self._context.notify_event(
                    set({entity}),
                    AgentEvent(
                        message_content=_generate_equipment_clothing_prompt(
                            actor_name, prop_file
                        )
                    ),
                )

                self.on_add_update_apperance_action(entity)

    ####################################################################################################################################
    def on_add_update_apperance_action(self, entity: Entity) -> None:
        # if not entity.has(UpdateAppearanceAction):
        #     entity.add(
        #         UpdateAppearanceAction,
        #         self._context.safe_get_entity_name(entity),
        #         [],
        #     )
        entity.replace(
            UpdateAppearanceAction,
            self._context.safe_get_entity_name(entity),
            [],
        )

    ####################################################################################################################################
