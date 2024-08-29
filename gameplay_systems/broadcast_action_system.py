from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import override, cast
from gameplay_systems.components import StageComponent, ActorComponent
from gameplay_systems.action_components import BroadcastAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from rpg_game.rpg_game import RPGGame
import file_system.helper

class BroadcastActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(BroadcastAction): GroupEvent.ADDED}

    ####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(BroadcastAction)

    ####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)
            #self.add_archive(entity)

    ####################################################################################################
    ## 目前的设定是场景与Actor都能广播，后续会调整与修改。
    def handle(self, entity: Entity) -> None:
        current_stage_entity = self._context.safe_get_stage_entity(entity)
        if current_stage_entity is None:
            return

        broadcast_action = entity.get(BroadcastAction)

        message = builtin_prompt.make_broadcast_action_prompt(
            broadcast_action.name,
            cast(str, current_stage_entity.get(StageComponent).name),
            " ".join(broadcast_action.values),
        )

        self._context.add_agent_context_message(set({current_stage_entity}), message)

    ####################################################################################################
    # def add_archive(self, entity: Entity) -> None:
    #     current_stage_entity = self._context.safe_get_stage_entity(entity)
    #     if current_stage_entity is None:
    #         return
        
    #     my_name = self._context.safe_get_entity_name(entity)

    #     for actor_entity in self._context.get_actors_in_stage(current_stage_entity):
    #         if entity == actor_entity:
    #             continue
            
    #         if entity.has(ActorComponent):
    #             file_system.helper.add_actor_archive_files(
    #                 self._context._file_system,
    #                 self._context.safe_get_entity_name(actor_entity),
    #                 set({my_name}),
    #             )
    #         elif entity.has(StageComponent):
    #             file_system.helper.add_stage_archive_files(
    #                 self._context._file_system,
    #                 self._context.safe_get_entity_name(actor_entity),
    #                 set({my_name}),
    #             )

        ####################################################################################################


