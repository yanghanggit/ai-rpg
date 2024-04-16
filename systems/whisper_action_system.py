from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import WhisperActionComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from typing import Optional
from loguru import logger
from auxiliary.dialogue_rule import parse_target_and_message, check_speak_enable
from auxiliary.director_component import DirectorComponent
from auxiliary.director_event import WhisperEvent


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
        logger.debug("<<<<<<<<<<<<<  WhisperActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.whisper(entity)  # 核心处理 
####################################################################################################
    def whisper(self, entity: Entity) -> None:
        whispercomp: WhisperActionComponent = entity.get(WhisperActionComponent)
        action: ActorAction = whispercomp.action
        for value in action.values:

            parse = parse_target_and_message(value)
            targetname: Optional[str] = parse[0]
            message: Optional[str] = parse[1]
            
            if targetname is None or message is None:
                logger.warning(f"目标{targetname}不存在，无法进行交谈。")
                continue

            if not check_speak_enable(self.context, entity, targetname):
                # 如果检查不过就能继续
                logger.error("check_speak_enable 检查失败")
                continue

            # 通知导演
            self.notifydirector(entity, targetname, message)
####################################################################################################
    def notifydirector(self, entity: Entity, targetname: str, message: str) -> None:
        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        safename = self.context.safe_get_entity_name(entity)
        if safename == "":
            return
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        directorcomp.addevent(WhisperEvent(safename, targetname, message))
####################################################################################################
        
            
        
                