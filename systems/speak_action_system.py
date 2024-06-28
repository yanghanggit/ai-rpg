from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from systems.components import SpeakActionComponent
from actor_plan_and_action.actor_action import ActorAction
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from gameplay_checks.conversation_check import conversation_check, ErrorConversationEnable
from systems.stage_director_component import notify_stage_director
from systems.stage_director_event import IStageDirectorEvent
from typing import override
from builtin_prompt.cn_builtin_prompt import speak_action_prompt



####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class StageOrActorSpeakEvent(IStageDirectorEvent):

    def __init__(self, who_is_speaking: str, who_is_target: str, message: str) -> None:
        self.who_is_speaking = who_is_speaking
        self.who_is_target = who_is_target
        self.message = message

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        speakcontent: str = speak_action_prompt(self.who_is_speaking, self.who_is_target, self.message, extended_context)
        return speakcontent
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        speakcontent: str = speak_action_prompt(self.who_is_speaking, self.who_is_target, self.message, extended_context)
        return speakcontent
####################################################################################################################################
class SpeakActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SpeakActionComponent): GroupEvent.ADDED}
####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SpeakActionComponent)
####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.speak(entity)  
####################################################################################################################################
    def speak(self, entity: Entity) -> None:
        speak_comp: SpeakActionComponent = entity.get(SpeakActionComponent)
        speak_action: ActorAction = speak_comp.action
        safe_name = self.context.safe_get_entity_name(entity)
        target_and_message = speak_action.target_and_message_values()
        for tp in target_and_message:
            target = tp[0]
            message = tp[1]
            if conversation_check(self.context, entity, target) != ErrorConversationEnable.VALID:
                continue
            notify_stage_director(self.context, entity, StageOrActorSpeakEvent(safe_name, target, message))
####################################################################################################################################
