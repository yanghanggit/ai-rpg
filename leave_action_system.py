
from entitas import Matcher, ReactiveProcessor, GroupEvent
from components import LeaveActionComponent

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################   
class LeaveActionSystem(ReactiveProcessor):

    def __init__(self, context) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(LeaveActionComponent): GroupEvent.ADDED}

    def filter(self, entity):
        return entity.has(LeaveActionComponent)

    def react(self, entities):
        print("<<<<<<<<<<<<<  LeaveActionSystem >>>>>>>>>>>>>>>>>")
        for entity in entities:
            #print(entity.get(LeaveActionComponent).context)
            entity.remove(LeaveActionComponent)    