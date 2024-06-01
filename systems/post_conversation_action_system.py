from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import SpeakActionComponent, BroadcastActionComponent, WhisperActionComponent, PlayerComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.dialogue_rule import dialogue_enable, parse_target_and_message, ErrorDialogueEnable
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import IDirectorEvent
from typing import Optional
from auxiliary.cn_builtin_prompt import speak_action_prompt

#post_conversation_action_system

# ####################################################################################################################################
# ####################################################################################################################################
# ####################################################################################################################################
# class SpeakEvent(IDirectorEvent):

#     def __init__(self, who_is_speaking: str, who_is_target: str, message: str) -> None:
#         self.who_is_speaking = who_is_speaking
#         self.who_is_target = who_is_target
#         self.message = message

#     def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
#         speakcontent: str = speak_action_prompt(self.who_is_speaking, self.who_is_target, self.message, extended_context)
#         return speakcontent
    
#     def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
#         speakcontent: str = speak_action_prompt(self.who_is_speaking, self.who_is_target, self.message, extended_context)
#         return speakcontent
####################################################################################################
class PostConversationActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher( any_of=[SpeakActionComponent, BroadcastActionComponent, WhisperActionComponent]): GroupEvent.ADDED}
####################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayerComponent)
####################################################################################################
    def react(self, entities: list[Entity]) -> None:
        pass
        # for entity in entities:
        #     self.speak(entity)  
####################################################################################################
    # def speak(self, entity: Entity) -> None:
    #     speakcomp: SpeakActionComponent = entity.get(SpeakActionComponent)
    #     speakaction: ActorAction = speakcomp.action
    #     safe_npc_name = self.context.safe_get_entity_name(entity)
    #     for value in speakaction.values:

    #         parse = parse_target_and_message(value)
    #         targetname: Optional[str] = parse[0]
    #         message: Optional[str] = parse[1]
            
    #         if targetname is None or message is None:
    #             continue
    
    #         if dialogue_enable(self.context, entity, targetname) != ErrorDialogueEnable.VALID:
    #             continue

    #         notify_stage_director(self.context, entity, SpeakEvent(safe_npc_name, targetname, message))
####################################################################################################
