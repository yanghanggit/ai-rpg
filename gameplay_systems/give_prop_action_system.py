from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from gameplay_systems.action_components import GivePropAction, CheckStatusAction, DeadAction
from gameplay_systems.components import ActorComponent
from loguru import logger
import gameplay_systems.conversation_helper
from typing import List, override
import gameplay_systems.cn_builtin_prompt as builtin_prompt
import file_system.helper
from file_system.files_def import PropFile
import my_format_string.target_and_message_format_string


class GivePropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext):
        super().__init__(context)
        self._context: RPGEntitasContext = context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(GivePropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GivePropAction)
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

        give_prop_action = entity.get(GivePropAction)
        target_and_message = (
            my_format_string.target_and_message_format_string.target_and_message_values(
                give_prop_action.values
            )
        )

        for tp in target_and_message:

            if (
                gameplay_systems.conversation_helper.check_conversation(
                    self._context, entity, tp[0]
                )
                != gameplay_systems.conversation_helper.ErrorConversation.VALID
            ):
                # 不能交谈就是不能交换道具
                continue

            handle_result = self.give_prop(entity, tp[0], tp[1])

            target_entity = self._context.get_actor_entity(tp[0])
            assert target_entity is not None

            self._context.add_agent_context_message(
                set({entity, target_entity}),
                builtin_prompt.make_give_prop_action_prompt(
                    self._context.safe_get_entity_name(entity),
                    tp[0],
                    tp[1],
                    handle_result,
                ),
            )

    ####################################################################################################################################
    def give_prop(self, entity: Entity, target_actor_name: str, prop_name: str) -> bool:
        safe_name = self._context.safe_get_entity_name(entity)

        prop_file = self._context._file_system.get_file(PropFile, safe_name, prop_name)
        if prop_file is None:
            return False

        file_system.helper.give_prop_file(
            self._context._file_system, safe_name, target_actor_name, prop_name
        )
        return True


####################################################################################################################################
