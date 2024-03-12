
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent
from components import StageComponent, NPCComponent, SpeakActionComponent
from actor_action import ActorAction

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################    
class SpeakActionSystem(ReactiveProcessor):

    def __init__(self, context) -> None:
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
                stagecomp = self.getstage(entity)
                if stagecomp is not None:
                    stagecomp.events.append(f"{action.name} 说（或者心里活动）: {value}")

            print("++++++++++++++++++++++++++++++++++++++++++++++++")

        # 必须移除！！！
        for entity in entities:
            entity.remove(SpeakActionComponent)     

    def getstage(self, entity: Entity) -> StageComponent:
        if entity.has(StageComponent):
            return entity.get(StageComponent)

        elif entity.has(NPCComponent):
            current_stage_name = entity.get(NPCComponent).current_stage
            for stage in self.context.get_group(Matcher(StageComponent)).entities:
                if stage.get(StageComponent).name == current_stage_name:
                    return stage.get(StageComponent)
        return None