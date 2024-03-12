
from entitas import Matcher, ReactiveProcessor, GroupEvent
from components import FightActionComponent


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################    
class FightActionSystem(ReactiveProcessor):

    def __init__(self, context) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(FightActionComponent): GroupEvent.ADDED}

    def filter(self, entity):
        return entity.has(FightActionComponent)

    def react(self, entities):
        print("<<<<<<<<<<<<<  FightActionSystem >>>>>>>>>>>>>>>>>")
        for entity in entities:
            #print(entity.get(FightActionComponent).context)
            entity.remove(FightActionComponent)         