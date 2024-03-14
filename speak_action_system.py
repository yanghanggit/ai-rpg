
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent
from components import SpeakActionComponent, NPCComponent, StageComponent
from actor_action import ActorAction
from extended_context import ExtendedContext
from typing import List

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################    
class SpeakActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(SpeakActionComponent): GroupEvent.ADDED}

    def filter(self, entity: list[Entity]):
        return entity.has(SpeakActionComponent)

    def react(self, entities: list[Entity]):
        print("<<<<<<<<<<<<<  SpeakActionSystem  >>>>>>>>>>>>>>>>>")
        self.handlememory(entities)
        self.handlespeak(entities)
        # 必须移除！！！
        for entity in entities:
            entity.remove(SpeakActionComponent)     

    def handlespeak(self, entities: list[Entity]) -> None:
        # 开始处理
        for entity in entities:
            speakcomp = entity.get(SpeakActionComponent)
            action: ActorAction = speakcomp.action
            for value in action.values:
                stagecomp = self.context.get_stage_by_entity(entity)
                if stagecomp is not None:
                    stagecomp.directorscripts.append(f"{action.name} 说（或者心里活动）: {value}")
        
    def handlememory(self, entities: list[Entity]) -> None:
        return
        for entity in entities:
            speakcomp = entity.get(SpeakActionComponent)
            action: ActorAction = speakcomp.action

            if entity.has(NPCComponent):
                npccomp = entity.get(NPCComponent)
                agent = npccomp.agent
                for value in action.values:
                    agent.add_chat_history(f"你说（或者心里活动）: {value}")
            elif entity.has(StageComponent):
                stagecomp = entity.get(StageComponent)
                agent = stagecomp.agent
                for value in action.values:
                    agent.add_chat_history(f"你说（或者心里活动）: {value}")
                