from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from my_components.action_components import WhisperAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override
import gameplay_systems.action_utils
import my_format_string.target_and_message_format_string
from rpg_game.rpg_game import RPGGame
from my_models.event_models import WhisperEvent


################################################################################################################################################
def _generate_whisper_prompt(
    whisperer_name: str, target_name: str, content: str
) -> str:
    return f"# 发生事件: {whisperer_name} 对 {target_name} 私语: {content}"


####################################################################################################################################
@final
class WhisperActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(WhisperAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(WhisperAction)

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_whisper_action(entity)

    ####################################################################################################################################
    def _process_whisper_action(self, entity: Entity) -> None:
        whisper_action = entity.get(WhisperAction)
        target_and_message = (
            my_format_string.target_and_message_format_string.target_and_message_values(
                whisper_action.values
            )
        )

        for tp in target_and_message:
            if (
                gameplay_systems.action_utils.validate_conversation(
                    self._context, entity, tp[0]
                )
                != gameplay_systems.action_utils.ConversationError.VALID
            ):
                continue

            target_entity = self._context.get_entity_by_name(tp[0])
            assert target_entity is not None

            # 注意，只有说话者和目标之间的私语才会被广播
            self._context.notify_event(
                set({entity, target_entity}),
                WhisperEvent(
                    message=_generate_whisper_prompt(whisper_action.name, tp[0], tp[1]),
                    whisperer_name=whisper_action.name,
                    target_name=tp[0],
                    content=tp[1],
                ),
            )


####################################################################################################################################
