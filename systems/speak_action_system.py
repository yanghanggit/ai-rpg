
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import SpeakActionComponent, NPCComponent, StageComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from agents.tools.print_in_color import Color
from auxiliary.prompt_maker import speak_action_prompt
from typing import Optional
from loguru import logger # type: ignore
   
####################################################################################################
class SpeakActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SpeakActionComponent): GroupEvent.ADDED}

    def filter(self, entity: Entity) -> bool:
        return entity.has(SpeakActionComponent)

    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  SpeakActionSystem  >>>>>>>>>>>>>>>>>")
        # 核心执行
        for entity in entities:
            self.handle(entity)  
        # 必须移除！！！
        for entity in entities:
            entity.remove(SpeakActionComponent)     
####################################################################################################
    def handle(self, entity: Entity) -> None:
        speakcomp = entity.get(SpeakActionComponent)
        action: ActorAction = speakcomp.action
        for value in action.values:
            tp = self.parsespeak(value)
            target = tp[0]
            message = tp[1]
            ##如果检查不过就能继续
            if not self.check_speak_enable(entity, target):
                continue
            ##拼接说话内容
            saycontent = speak_action_prompt(action.name, target, message, self.context)
            logger.info(f"{Color.HEADER}{saycontent}{Color.ENDC}")
            ##添加场景事件，最后随着导演剧本走
            stagecomp: Optional[StageComponent] = self.context.get_stagecomponent_by_uncertain_entity(entity)
            if stagecomp is not None:
                stagecomp.directorscripts.append(saycontent)
####################################################################################################
    def check_speak_enable(self, src: Entity, dstname: str) -> bool:

        npc_entity: Optional[Entity] = self.context.getnpc(dstname)
        if npc_entity is None:
            logger.warning(f"No NPC named {dstname} found")
            return False

        current_stage_comp: Optional[StageComponent] = self.context.get_stagecomponent_by_uncertain_entity(src)  
        if current_stage_comp is None:
            logger.warning(f"StageComponent not found for {src}")
            return False  
        
        npccomp: NPCComponent = npc_entity.get(NPCComponent)
        if current_stage_comp.name != npccomp.current_stage:
            logger.warning(f"{src} is not in {npccomp.current_stage}, {current_stage_comp.name}")
            return False
        
        return True
####################################################################################################
    def parsespeak(self, content: str) -> tuple[str, str]:
        # 解析出说话者和说话内容
        target, message = content.split(">")
        target = target[1:]  # Remove the '@' symbol
        return target, message
       