from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import SpeakActionComponent, NPCComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.dialogue_rule import check_speak_enable, parse_target_and_message
from auxiliary.director_component import DirectorComponent
from auxiliary.director_event import NPCSpeakEvent
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
        return entity.has(SpeakActionComponent) and entity.has(NPCComponent)
####################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  SpeakActionSystem  >>>>>>>>>>>>>>>>>")
        # 核心执行
        for entity in entities:
            self.speak(entity)  
####################################################################################################
    def speak(self, entity: Entity) -> None:
        speak_comp: SpeakActionComponent = entity.get(SpeakActionComponent)
        speak_action: ActorAction = speak_comp.action
        for value in speak_action.values:

            parse = parse_target_and_message(value)
            targetname: Optional[str] = parse[0]
            message: Optional[str] = parse[1]
            
            if targetname is None or message is None:
                logger.warning(f"目标{targetname}不存在，无法进行交谈。")
                continue
            
            ##如果检查不过就能继续
            if not check_speak_enable(self.context, entity, targetname):
                logger.error("check_speak_enable 检查失败")
                continue
            
            # 通知导演
            self.notifydirector(entity, targetname, message)
####################################################################################################
    def notifydirector(self, entity: Entity, targetname: str, message: str) -> None:
        if not entity.has(NPCComponent):
            return
        
        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        
        npccomp: NPCComponent = entity.get(NPCComponent)
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        directorcomp.addevent(NPCSpeakEvent(npccomp.name, targetname, message))
####################################################################################################


       