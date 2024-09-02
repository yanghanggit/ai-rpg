from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import override, cast, List
from gameplay_systems.action_components import RemovePropAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from file_system.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from gameplay_systems.components import ActorComponent, StageComponent


############################################################################################################
class RemovePropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(RemovePropAction): GroupEvent.ADDED}

    ############################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(RemovePropAction) and (
            entity.has(StageComponent) or entity.has(ActorComponent)
        )

    ############################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ############################################################################################################
    def handle(self, entity: Entity) -> None:
        remove_prop_action = entity.get(RemovePropAction)
        if len(remove_prop_action.values) == 0:
            return

        for prop_name in cast(List[str], remove_prop_action.values):

            prop_file = self._context._file_system.get_file(
                PropFile, remove_prop_action.name, prop_name
            )
            if prop_file is None:
                self.on_prop_lost_event(entity, prop_name)
                continue

            self._context._file_system.remove_file(prop_file)
            self.on_prop_remove_event(entity, prop_name)

    ############################################################################################################
    def on_prop_lost_event(self, entity: Entity, prop_name: str) -> None:
        safe_name = self._context.safe_get_entity_name(entity)

        if entity.has(StageComponent):
            self._context.add_agent_context_message(
                set({entity}),
                builtin_prompt.make_stage_prop_lost_prompt(safe_name, prop_name),
            )

    ############################################################################################################
    def on_prop_remove_event(self, entity: Entity, prop_name: str) -> None:
        safe_name = self._context.safe_get_entity_name(entity)

        if entity.has(StageComponent):
            self._context.add_agent_context_message(
                set({entity}),
                builtin_prompt.make_stage_prop_remove_prompt(safe_name, prop_name),
            )

    ############################################################################################################
