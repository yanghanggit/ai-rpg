from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import SpeakActionComponent
from auxiliary.actor_plan_and_action import ActorAction
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from auxiliary.target_and_message_format_handle import conversation_check, parse_target_and_message, ErrorConversationEnable
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import IDirectorEvent
from typing import Optional, override
from builtin_prompt.cn_builtin_prompt import speak_action_prompt



####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class StageOrActorSpeakEvent(IDirectorEvent):

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
####################################################################################################
class SpeakActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SpeakActionComponent): GroupEvent.ADDED}
####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SpeakActionComponent)
####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.speak(entity)  
####################################################################################################
    def speak(self, entity: Entity) -> None:
        speakcomp: SpeakActionComponent = entity.get(SpeakActionComponent)
        speakaction: ActorAction = speakcomp.action
        safe_name = self.context.safe_get_entity_name(entity)
        for value in speakaction.values:

            parse = parse_target_and_message(value)
            targetname: Optional[str] = parse[0]
            message: Optional[str] = parse[1]
            
            if targetname is None or message is None:
                continue
    
            if conversation_check(self.context, entity, targetname) != ErrorConversationEnable.VALID:
                continue

            notify_stage_director(self.context, entity, StageOrActorSpeakEvent(safe_name, targetname, message))
####################################################################################################
