from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import SpeakActionComponent, NPCComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from auxiliary.print_in_color import Color
from auxiliary.prompt_maker import speak_action_prompt, speak_action_system_invalid_target
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
        return entity.has(SpeakActionComponent)
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
            tagret_message_pair = parse_target_and_message(value)
            target: Optional[str] = tagret_message_pair[0]
            message: Optional[str] = tagret_message_pair[1]
            if target is None or message is None:
                logger.warning(f"目标{target}不存在，无法进行交谈。")
                continue
            ##如果检查不过就能继续
            if not check_speak_enable(self.context, entity, target):
                # 加一个历史，让NPC在下一次的request中再仔细琢磨一下。
                addchat = speak_action_system_invalid_target(target, message)
                self.context.safe_add_human_message_to_entity(entity, addchat)
                continue
            
            ##拼接说话内容
            say_content: str = speak_action_prompt(speak_action.name, target, message, self.context)
            logger.info(f"{Color.HEADER}{say_content}{Color.ENDC}")
            self.add_event_to_director(entity, target, message)
####################################################################################################
    def add_event_to_director(self, entity: Entity, targetname: str, message: str) -> None:
        if entity is None or not entity.has(NPCComponent):
            ##写死，只有NPC才能说话
            return
        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None or not stageentity.has(DirectorComponent):
            # 不带这个组件就不能继续
            return
        #
        npccomp: NPCComponent = entity.get(NPCComponent)
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        speakevent = NPCSpeakEvent(npccomp.name, targetname, message)
        directorcomp.addevent(speakevent)
####################################################################################################


       