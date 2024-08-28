from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from gameplay_systems.action_components import (
    StealPropAction,
    DeadAction,
)
from gameplay_systems.components import ActorComponent
import gameplay_systems.conversation_helper
from typing import override
import gameplay_systems.cn_builtin_prompt as builtin_prompt
import file_system.helper
from file_system.files_def import PropFile
import my_format_string.target_and_message_format_string
from rpg_game.rpg_game import RPGGame


class StealActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(StealPropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(StealPropAction)
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

        steal_action: StealPropAction = entity.get(StealPropAction)
        target_and_message = (
            my_format_string.target_and_message_format_string.target_and_message_values(
                steal_action.values
            )
        )

        for tp in target_and_message:

            if (
                gameplay_systems.conversation_helper.check_conversation(
                    self._context, entity, tp[0]
                )
                != gameplay_systems.conversation_helper.ErrorConversation.VALID
            ):
                # 不能交谈就是不能偷
                continue

            safe_name = self._context.safe_get_entity_name(entity)
            target_entity = self._context.get_entity_by_name(tp[0])
            assert target_entity is not None

            handle_result = self.steal(entity, tp[0], tp[1])

            self._context.add_agent_context_message(
                set({entity, target_entity}),
                builtin_prompt.make_steal_prop_action_prompt(
                    safe_name, tp[0], tp[1], handle_result
                ),
            )

    ####################################################################################################################################
    def steal(self, entity: Entity, target_actor_name: str, prop_name: str) -> bool:
        prop_file = self._context._file_system.get_file(
            PropFile, target_actor_name, prop_name
        )
        if prop_file is None:
            return False
        file_system.helper.give_prop_file(
            self._context._file_system,
            target_actor_name,
            self._context.safe_get_entity_name(entity),
            prop_name,
        )
        return True


####################################################################################################################################
