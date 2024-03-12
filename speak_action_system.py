
from entitas import Matcher, ReactiveProcessor, GroupEvent
from components import SpeakActionComponent
from actor_action import ActorAction
from extended_context import ExtendedContext

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

    def filter(self, entity):
        return entity.has(SpeakActionComponent)

    def react(self, entities):
        print("<<<<<<<<<<<<<  SpeakActionSystem >>>>>>>>>>>>>>>>>")

        # 开始处理
        for entity in entities:
            comp = entity.get(SpeakActionComponent)
            action: ActorAction = comp.action
            for value in action.values:
                print(f"[{action.name}] /speak:", value)
                stagecomp = self.context.get_stage_by_entity(entity)
                if stagecomp is not None:
                    self.context.add_stage_events(stagecomp.name, f"{action.name} 说（或者心里活动）: {value}")
            print("++++++++++++++++++++++++++++++++++++++++++++++++")

        # 必须移除！！！
        for entity in entities:
            entity.remove(SpeakActionComponent)     