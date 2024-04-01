
from entitas import Matcher, ExecuteProcessor, Entity #type: ignore
from auxiliary.components import (DeadActionComponent, 
                        LeaveForActionComponent, 
                        SearchActionComponent, 
                        DestroyComponent,
                        NPCComponent)
from auxiliary.extended_context import ExtendedContext
from auxiliary.actor_agent import ActorAgent
from auxiliary.prompt_maker import gen_npc_archive_prompt, npc_memory_before_death
from loguru import logger
from auxiliary.agent_connect_system import AgentConnectSystem


class DeadActionSystem(ExecuteProcessor):
    
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context

    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  DeadActionSystem  >>>>>>>>>>>>>>>>>")
        # 如果死了先存档
        self.handle_save_when_npc_dead()
        # 然后处理剩下的事情，例如关闭一些行为与准备销毁组件
        self.handle_after_npc_dead()

    def handle_save_when_npc_dead(self) -> None:
         entities:set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities
         for entity in entities:
            self.save_npc(entity)

    def save_npc(self, entity: Entity) -> None:
        agent_connect_system = self.context.agent_connect_system
        if entity.has(NPCComponent):
            npccomp: NPCComponent = entity.get(NPCComponent)
            #npc_agent: ActorAgent = npc_comp.agent
            # 添加记忆
            mem_before_death = npc_memory_before_death(self.context)
            self.context.add_agent_memory(entity, mem_before_death)
            # 推理死亡，并且进行存档
            archive_prompt = gen_npc_archive_prompt(self.context)
            #archive = npc_agent.request(archive_prompt)
            archive = agent_connect_system.request2(npccomp.name, archive_prompt)

            if archive is not None:
                self.context.savearchive(archive, npccomp.name)
        else:
            raise ValueError("DeadActionSystem: 死亡的不是NPC！")
        
    def handle_after_npc_dead(self) -> None:
        entities:set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities
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
                entity.add(DestroyComponent, "why?")
            else:
                raise ValueError("DeadActionSystem: 已经有销毁组件了！")
        
            

        
             
            
        


    