
from entitas import Entity, Matcher, ExecuteProcessor
from components import StageComponent, NPCComponent
from typing import List
from extended_context import ExtendedContext


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################               
class DirectorSystem(ExecuteProcessor):
    
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  DirectorSystem >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entities:
            self.handle(entity)
            #清空
            comp = entity.get(StageComponent)
            comp.events.clear() #不能 = []，会报错！！！

    def handle(self, entity: Entity) -> None:
        stagecomp = entity.get(StageComponent)
        print(f"[{stagecomp.name}] 开始导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")

        events = self.context.get_stage_events(stagecomp.name)
        if len(events) == 0:
            return
    
        #debug
        # for event in events:
        #     print("moive:", event)

        allevents = "\n".join(events)
        director_prompt =  f"""
        # 你按着我的给你的脚本来演绎过程，并适当润色让过程更加生动。
        ## 剧本如下
        - {allevents}
        ## 步骤
        - 第1步：理解我的剧本
        - 第2步：根据剧本，完善你的故事讲述(同一个人物的行为描述要合并处理)。要保证和脚本的结果一致。
        - 第3步：更新你的记忆
        ## 输出规则
        - 输出在保证语意完整基础上字符尽量少。
        """
        #
        response = stagecomp.agent.request(director_prompt)
        npcs_in_stage = self.context.get_npcs_in_stage(stagecomp.name)
        npcs_names = "\n".join([npc.get(NPCComponent).name for npc in npcs_in_stage])
        confirm_prompt = f"""
        # 你目睹或者参与了这一切，并更新了你的记忆
        - {response}
        # 你能确认
        - {npcs_names} 都还在此 {stagecomp.name} 场景中。
        """

        for npcen in npcs_in_stage:
            ncomp = npcen.get(NPCComponent)
            response = ncomp.agent.request(confirm_prompt)
            #print(f"[{ncomp.name}]=>", response)

        print(f"[{stagecomp.name}] 结束导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")


    def getnpcs(self, stage: str) -> List[NPCComponent]:
        npcs = []
        for entity in self.context.get_group(Matcher(NPCComponent)).entities:
            if entity.get(NPCComponent).current_stage == stage:
                npcs.append(entity.get(NPCComponent))
        return npcs