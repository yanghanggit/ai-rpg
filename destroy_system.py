
from entitas import Matcher,ExecuteProcessor
from components import DestroyComponent
from actor_action import ActorAction



###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################   
class DestroySystem(ExecuteProcessor):
    
    def __init__(self, context) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  DestroySystem >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(DestroyComponent)).entities
        for entity in entities:
             comp = entity.get(DestroyComponent)
             print(comp.cause)
             self.context.destroy_entity(entity)



    