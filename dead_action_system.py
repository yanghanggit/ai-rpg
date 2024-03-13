
from entitas import Matcher, ExecuteProcessor, Entity
from components import (DeadActionComponent, 
                        LeaveActionComponent, 
                        TagActionComponent, 
                        DestroyComponent,
                        NPCComponent)
from extended_context import ExtendedContext
from actor_agent import ActorAgent
from agents.tools.extract_md_content import wirte_content_into_md


class DeadActionSystem(ExecuteProcessor):
    
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  DeadActionSystem  >>>>>>>>>>>>>>>>>")
        entities:set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities
        for entity in entities:
            if entity.has(LeaveActionComponent):
                entity.remove(LeaveActionComponent)
             
            if entity.has(TagActionComponent):
                entity.remove(TagActionComponent)
            
            if not entity.has(DestroyComponent):
                entity.add(DestroyComponent, "Dead")
                if entity.has(NPCComponent):
                    npc_comp:NPCComponent = entity.has(NPCComponent)
                    npc_agent: ActorAgent = npc_comp.agent
                    archive_prompt = """
            请根据上下文，对自己知道的事情进行梳理总结成markdown格式后输出,但不要生成```markdown xxx```的形式:
            # 游戏世界存档
            ## 地点
            ### xxx
            #### 发生的事件
            - xx时间，xxx
            - xx时间，xxx
            - xx时间，xxx
            ### xxx
            #### 发生的事件
            - xx时间，xxx
            - xx时间，xxx
            - xx时间，xxx
            """
            archive = npc_agent.request(archive_prompt)
            # print(f"{agent.name}:\n{archive}")
            wirte_content_into_md(archive, f"/savedData/{npc_agent.name}.md")

        
             
            
        


    