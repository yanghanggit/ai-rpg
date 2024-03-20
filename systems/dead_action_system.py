
from entitas import Matcher, ExecuteProcessor, Entity #type: ignore
from auxiliary.components import (DeadActionComponent, 
                        LeaveForActionComponent, 
                        SearchActionComponent, 
                        DestroyComponent,
                        NPCComponent)
from auxiliary.extended_context import ExtendedContext
from auxiliary.actor_agent import ActorAgent
from auxiliary.prompt_maker import gen_npc_archive_prompt, npc_memory_before_death
from loguru import logger #type: ignore


class DeadActionSystem(ExecuteProcessor):
    
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context

    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  DeadActionSystem  >>>>>>>>>>>>>>>>>")
        entities:set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities

        ##如果死的是NPC，就要保存存档
        for entity in entities:
            self.save_when_npc_dead(entity)

        #核心处理，如果死了就要处理下面的组件
        for entity in entities:

            #死了的不允许再搜索
            if entity.has(SearchActionComponent):
                entity.remove(SearchActionComponent)

            #死了的不允许再离开
            if entity.has(LeaveForActionComponent):
                entity.remove(LeaveForActionComponent)
             
            #死了的需要准备销毁
            if not entity.has(DestroyComponent):
                entity.add(DestroyComponent, "from DeadActionSystem")


    def save_when_npc_dead(self, entity: Entity) -> None:
        if entity.has(NPCComponent):
            npc_comp: NPCComponent = entity.get(NPCComponent)
            npc_agent: ActorAgent = npc_comp.agent
            # 添加记忆
            mem_before_death = npc_memory_before_death(self.context)
            self.context.add_agent_memory(entity, mem_before_death)
            # 推理死亡，并且进行存档
            archive_prompt = gen_npc_archive_prompt(self.context)
            archive = npc_agent.request(archive_prompt)
            self.context.savearchive(archive, npc_agent.name)

        
             
            
        


    