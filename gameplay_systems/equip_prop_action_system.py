from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from gameplay_systems.action_components import (
    EquipPropAction,
    DeadAction,
    UpdateAppearanceAction,
)
from gameplay_systems.components import (
    ActorComponent,
    RPGCurrentWeaponComponent,
    RPGCurrentClothesComponent,
)
from loguru import logger
from typing import override
from file_system.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from rpg_game.rpg_game import RPGGame


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
                continue

            if prop_file.is_weapon:

                entity.replace(
                    RPGCurrentWeaponComponent, equip_prop_action.name, prop_name
                )

                self._context.add_agent_context_message(
                    set({entity}),
                    builtin_prompt.make_equip_prop_weapon_prompt(actor_name, prop_file),
                )

            elif prop_file.is_clothes:

                entity.replace(
                    RPGCurrentClothesComponent, equip_prop_action.name, prop_name
                )

                self._context.add_agent_context_message(
                    set({entity}),
                    builtin_prompt.make_equip_prop_clothes_prompt(
                        actor_name, prop_file
                    ),
                )

                self.on_add_update_apperance_action(entity)

    ####################################################################################################################################
    def on_add_update_apperance_action(self, entity: Entity) -> None:
        if not entity.has(UpdateAppearanceAction):
            entity.add(
                UpdateAppearanceAction,
                self._context.safe_get_entity_name(entity),
                UpdateAppearanceAction.__name__,
                [],
            )

    ####################################################################################################################################
