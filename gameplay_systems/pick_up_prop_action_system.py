from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from gameplay_systems.action_components import PickUpPropAction, DeadAction
from gameplay_systems.components import ActorComponent, StageComponent
from loguru import logger
from typing import override
from extended_systems.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
import extended_systems.file_system_helper
from rpg_game.rpg_game import RPGGame


class PickUpPropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PickUpPropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PickUpPropAction)
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

        pick_up_prop_action = entity.get(PickUpPropAction)
        if len(pick_up_prop_action.values) == 0:
            return

        current_stage_entity = self._context.safe_get_stage_entity(entity)
        if current_stage_entity is None:
            logger.error(f"current_stage_entity is None")
            return

        actor_name = self._context.safe_get_entity_name(entity)
        stage_comp = current_stage_entity.get(StageComponent)

        for prop_name in pick_up_prop_action.values:

            prop_file = self._context._file_system.get_file(
                PropFile, stage_comp.name, prop_name
            )
            if prop_file is None:
                self._context.broadcast_entities(
                    set({entity}),
                    builtin_prompt.make_actor_pick_up_prop_failed_prompt(
                        actor_name, prop_name
                    ),
                )
                continue

            extended_systems.file_system_helper.give_prop_file(
                self._context._file_system,
                stage_comp.name,
                pick_up_prop_action.name,
                prop_name,
            )

            self._context.broadcast_entities_in_stage(
                current_stage_entity,
                builtin_prompt.make_pick_up_prop_success_prompt(
                    actor_name, prop_name, stage_comp.name
                ),
            )

            # 写死的，只能拾取一次。
            break

    ####################################################################################################################################
