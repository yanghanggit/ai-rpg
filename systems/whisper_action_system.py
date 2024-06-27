from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import WhisperActionComponent
from auxiliary.actor_plan_and_action import ActorAction
from my_entitas.extended_context import ExtendedContext
from typing import Optional, override
from loguru import logger
from auxiliary.target_and_message_format_handle import parse_target_and_message, conversation_check, ErrorConversationEnable
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import IDirectorEvent
from builtin_prompt.cn_builtin_prompt import whisper_action_prompt


####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class StageOrActorWhisperEvent(IDirectorEvent):
    
    def __init__(self, who_is_whispering: str, who_is_target: str, message: str) -> None:
        self.who_is_whispering = who_is_whispering
        self.who_is_target = who_is_target
        self.message = message

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self.who_is_whispering or actor_name != self.who_is_target:
            # 只有这2个人才能听到
            return ""
        whispercontent = whisper_action_prompt(self.who_is_whispering, self.who_is_target, self.message, extended_context)
        return whispercontent
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        ## 场景应该是彻底听不到
        return ""
####################################################################################################
class WhisperActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(WhisperActionComponent): GroupEvent.ADDED}
####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(WhisperActionComponent)
####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.whisper(entity) 
####################################################################################################
    def whisper(self, entity: Entity) -> None:
        whispercomp: WhisperActionComponent = entity.get(WhisperActionComponent)
        action: ActorAction = whispercomp.action
        safe_name = self.context.safe_get_entity_name(entity)

        for value in action.values:

            parse = parse_target_and_message(value)
            targetname: Optional[str] = parse[0]
            message: Optional[str] = parse[1]
            
            if targetname is None or message is None:
                continue

            if conversation_check(self.context, entity, targetname) != ErrorConversationEnable.VALID:
                continue
            
            notify_stage_director(self.context, entity, StageOrActorWhisperEvent(safe_name, targetname, message))
####################################################################################################
