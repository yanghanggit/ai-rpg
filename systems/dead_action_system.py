
from entitas import Matcher, ExecuteProcessor, Entity #type: ignore
from auxiliary.components import (DeadActionComponent, 
                        DestroyComponent)
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.actor_action import ActorAction

class DeadActionSystem(ExecuteProcessor):
    
########################################################################################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
########################################################################################################################################################################
    def execute(self) -> None:
        self.destoryentity()
########################################################################################################################################################################  
    def destoryentity(self) -> None:
        entities: set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities
        for entity in entities:
            deadcomp: DeadActionComponent = entity.get(DeadActionComponent)
            action: ActorAction = deadcomp.action
            if not entity.has(DestroyComponent):
                entity.add(DestroyComponent, action.name) ### 这里只需要名字，不需要values，谁造成了你的死亡
########################################################################################################################################################################
            

        
             
            
        


    