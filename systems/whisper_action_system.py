from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import WhisperActionComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from typing import Optional
from loguru import logger
from auxiliary.dialogue_rule import parse_target_and_message, dialogue_enable, ErrorDialogueEnable
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import IDirectorEvent
from auxiliary.cn_builtin_prompt import whisper_action_prompt


####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class WhisperEvent(IDirectorEvent):
    
    def __init__(self, who_is_whispering: str, who_is_target: str, message: str) -> None:
        self.who_is_whispering = who_is_whispering
        self.who_is_target = who_is_target
        self.message = message

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.who_is_whispering or npcname != self.who_is_target:
            # 只有这2个人才能听到
            return ""
        whispercontent = whisper_action_prompt(self.who_is_whispering, self.who_is_target, self.message, extended_context)
        return whispercontent
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        ## 场景应该是彻底听不到
        return ""
####################################################################################################
class WhisperActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(WhisperActionComponent): GroupEvent.ADDED}
####################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(WhisperActionComponent)
####################################################################################################
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.whisper(entity) 
####################################################################################################
    def whisper(self, entity: Entity) -> None:
        whispercomp: WhisperActionComponent = entity.get(WhisperActionComponent)
        action: ActorAction = whispercomp.action
        safe_npc_name = self.context.safe_get_entity_name(entity)

        for value in action.values:

            parse = parse_target_and_message(value)
            targetname: Optional[str] = parse[0]
            message: Optional[str] = parse[1]
            
            if targetname is None or message is None:
                continue

            if dialogue_enable(self.context, entity, targetname) != ErrorDialogueEnable.VALID:
                continue
            
            notify_stage_director(self.context, entity, WhisperEvent(safe_npc_name, targetname, message))
####################################################################################################
