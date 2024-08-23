from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from ecs_systems.action_components import SpeakAction

# from my_agent.agent_action import AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
import gameplay.conversation_helper

# from ecs_systems.stage_director_component import StageDirectorComponent
# from ecs_systems.stage_director_event import IStageDirectorEvent
from typing import override
import ecs_systems.cn_builtin_prompt as builtin_prompt
import my_format_string.target_and_message_format_string


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
# class StageOrActorSpeakEvent(IStageDirectorEvent):

#     def __init__(self, who: str, target: str, message: str) -> None:
#         self._who: str = who
#         self._target: str = target
#         self._message: str = message

#     def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
#         return builtin_prompt.make_speak_action_prompt(
#             self._who, self._target, self._message
#         )

#     def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
#         return builtin_prompt.make_speak_action_prompt(
#             self._who, self._target, self._message
#         )


####################################################################################################################################
class SpeakActionSystem(ReactiveProcessor):
    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context = context

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
            self.speak(entity)

    ####################################################################################################################################
    def speak(self, entity: Entity) -> None:
        speak_action = entity.get(SpeakAction)
        # speak_action: AgentAction = speak_comp.action
        safe_name = self._context.safe_get_entity_name(entity)
        target_and_message = (
            my_format_string.target_and_message_format_string.target_and_message_values(
                speak_action.values
            )
        )
        # speak_action.target_and_message_values()
        for tp in target_and_message:
            target = tp[0]
            message = tp[1]
            if (
                gameplay.conversation_helper.check_conversation_enable(
                    self._context, entity, target
                )
                != gameplay.conversation_helper.ErrorConversationEnable.VALID
            ):
                continue
            # StageDirectorComponent.add_event_to_stage_director(
            #     self._context,
            #     entity,
            #     StageOrActorSpeakEvent(safe_name, target, message),
            # )

            target_entity = self._context.get_entity_by_name(target)
            assert target_entity is not None

            #     return builtin_prompt.make_speak_action_prompt(
            #     self._who, self._target, self._message
            # )
            self._context.add_agent_context_message(
                set({entity, target_entity}),
                builtin_prompt.make_speak_action_prompt(safe_name, target, message),
            )


####################################################################################################################################
