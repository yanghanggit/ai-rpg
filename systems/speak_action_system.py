from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import SpeakActionComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.dialogue_rule import dialogue_enable, parse_target_and_message, ErrorDialogueEnable
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import SpeakEvent
from typing import Optional

   
####################################################################################################
class SpeakActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SpeakActionComponent): GroupEvent.ADDED}
####################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(SpeakActionComponent)
####################################################################################################
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.speak(entity)  
####################################################################################################
    def speak(self, entity: Entity) -> None:
        speakcomp: SpeakActionComponent = entity.get(SpeakActionComponent)
        speakaction: ActorAction = speakcomp.action
        safe_npc_name = self.context.safe_get_entity_name(entity)
        for value in speakaction.values:

            parse = parse_target_and_message(value)
            targetname: Optional[str] = parse[0]
            message: Optional[str] = parse[1]
            
            if targetname is None or message is None:
                continue
    
            if dialogue_enable(self.context, entity, targetname) != ErrorDialogueEnable.VALID:
                continue

            notify_stage_director(self.context, entity, SpeakEvent(safe_npc_name, targetname, message))
####################################################################################################
