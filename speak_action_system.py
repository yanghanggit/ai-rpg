
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent
from components import SpeakActionComponent, NPCComponent, StageComponent
from actor_action import ActorAction
from extended_context import ExtendedContext
from typing import List
from agents.tools.print_in_color import Color

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
        #self.handlememory(entities)
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
                stagecomp = self.context.get_stagecomponent_by_uncertain_entity(entity)
                if stagecomp is not None:
                    what_to_said = f"{action.name}说:{value}"
                    print(f"{Color.HEADER}{what_to_said}{Color.ENDC}")
                    stagecomp.directorscripts.append(what_to_said)