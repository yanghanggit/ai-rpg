from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from my_components.action_components import SpeakAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
import gameplay_systems.conversation_helper
from typing import final, override
import my_format_string.target_and_message_format_string
from rpg_game.rpg_game import RPGGame
from my_models.event_models import SpeakEvent


def _generate_speak_prompt(speaker_name: str, target_name: str, content: str) -> str:
    return f"# 发生事件: {speaker_name} 对 {target_name} 说: {content}"


####################################################################################################################################
@final
class SpeakActionSystem(ReactiveProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SpeakAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SpeakAction)

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_speak_action(entity)

    ####################################################################################################################################
    def _process_speak_action(self, entity: Entity) -> None:

        speak_action = entity.get(SpeakAction)
        target_and_message = (
            my_format_string.target_and_message_format_string.target_and_message_values(
                speak_action.values
            )
        )

        for tp in target_and_message:
            if (
                gameplay_systems.conversation_helper.validate_conversation(
                    self._context, entity, tp[0]
                )
                != gameplay_systems.conversation_helper.ConversationError.VALID
            ):
                continue

            assert self._context.get_entity_by_name(tp[0]) is not None
            self._context.broadcast_event_in_stage(
                entity,
                SpeakEvent(
                    message=_generate_speak_prompt(speak_action.name, tp[0], tp[1]),
                    speaker_name=speak_action.name,
                    target_name=tp[0],
                    content=tp[1],
                ),
            )


####################################################################################################################################
