
from entitas import Matcher, ExecuteProcessor, Entity #type: ignore
from auxiliary.components import (DeadActionComponent, 
                        LeaveForActionComponent, 
                        SearchActionComponent, 
                        DestroyComponent,
                        NPCComponent)
from auxiliary.extended_context import ExtendedContext
from auxiliary.prompt_maker import gen_npc_archive_prompt, npc_memory_before_death
from loguru import logger
from auxiliary.actor_action import ActorAction


class DeadActionSystem(ExecuteProcessor):
    
########################################################################################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
########################################################################################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  DeadActionSystem  >>>>>>>>>>>>>>>>>")
        # 如果死了先存档
        self.must_save_archive()
        # 然后处理剩下的事情，例如关闭一些行为与准备销毁组件
        self.some_actions_need_to_be_removed()
        # 最后销毁
        self.must_destory()
########################################################################################################################################################################
    def must_save_archive(self) -> None:
         entities:set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities
         for entity in entities:
            self.savenpc(entity)
########################################################################################################################################################################
    def savenpc(self, entity: Entity) -> None:
        agent_connect_system = self.context.agent_connect_system
        memory_system = self.context.memory_system
        if entity.has(NPCComponent):
            npccomp: NPCComponent = entity.get(NPCComponent)
            # 添加记忆
            mem_before_death = npc_memory_before_death(self.context)
            self.context.add_human_message_to_entity(entity, mem_before_death)
            # 推理死亡，并且进行存档
            archiveprompt = gen_npc_archive_prompt(self.context)
            archive = agent_connect_system.request(npccomp.name, archiveprompt)
            if archive is not None:
                # 存档!
                memory_system.overwritememory(npccomp.name, archive)
        else:
            raise ValueError("DeadActionSystem: 死亡的不是NPC！，能把场景打死算你厉害")
########################################################################################################################################################################    
    def some_actions_need_to_be_removed(self) -> None:
        entities:set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities
        #核心处理，如果死了就要处理下面的组件
        for entity in entities:
            #死了的不允许再搜索
            if entity.has(SearchActionComponent):
                entity.remove(SearchActionComponent)
            #死了的不允许再离开
            if entity.has(LeaveForActionComponent):
                entity.remove(LeaveForActionComponent)   
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
            else:
                raise ValueError("DeadActionSystem: 已经有销毁组件了！")
########################################################################################################################################################################
            

        
             
            
        


    