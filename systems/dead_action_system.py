
from entitas import Matcher, ExecuteProcessor, Entity #type: ignore
from auxiliary.components import (DeadActionComponent, 
                        DestroyComponent,
                        NPCComponent,
                        npc_interactive_actions_register)
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.actor_action import ActorAction

class DeadActionSystem(ExecuteProcessor):
    
########################################################################################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
########################################################################################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  DeadActionSystem  >>>>>>>>>>>>>>>>>")
        # 然后处理剩下的事情，例如关闭一些行为与准备销毁组件
        self.remove_npc_actions()
        # 最后销毁
        self.must_destory()
########################################################################################################################################################################    
    def remove_npc_actions(self) -> None:
        npcentities:set[Entity] = self.context.get_group(Matcher(all_of = [NPCComponent, DeadActionComponent])).entities
        #核心处理，如果死了就要处理下面的组件
        for entity in npcentities:
            for actionsclass in npc_interactive_actions_register:
                if entity.has(actionsclass):
                    entity.remove(actionsclass)
########################################################################################################################################################################  
    def must_destory(self) -> None:
        entities:set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities
        #核心处理，如果死了就要处理下面的组件
        for entity in entities:
            deadcomp: DeadActionComponent = entity.get(DeadActionComponent)
            action: ActorAction = deadcomp.action
            #死了的需要准备销毁
            if not entity.has(DestroyComponent):
                entity.add(DestroyComponent, action.name) ### 这里只需要名字，不需要values，谁造成了你的死亡
########################################################################################################################################################################
            

        
             
            
        


    