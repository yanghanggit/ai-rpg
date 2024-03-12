
from entitas import Entity, Matcher, ExecuteProcessor
from components import StageComponent, NPCComponent
from typing import List


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################               
class DirectorSystem(ExecuteProcessor):
    
    def __init__(self, context) -> None:
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
        comp = entity.get(StageComponent)
        print(f"[{comp.name}] 开始导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")
        if len(comp.events) == 0:
            return
    
        #debug
        for event in comp.events:
            print("moive:", event)

        allevents = "\n".join(comp.events)
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
        response = comp.agent.request(director_prompt)
        print("============================================================================")

        print(f"{comp.name}=>", response)


        npccomps = self.getnpcs(comp.name)
        all_names = "、".join([ncomp.name for ncomp in npccomps])

        confirm_prompt = f"""
        # 你目睹或者参与了这一切，并更新了你的记忆
        - {response}
        # 你能确认
        - {all_names} 都还存在。
        """

        for ncomp in npccomps:
            response = ncomp.agent.request(confirm_prompt)
            print(f"[{ncomp.name}]=>", response)


        print(f"[{comp.name}] 结束导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")


    def getnpcs(self, stage: str) -> List[NPCComponent]:
        npcs = []
        for entity in self.context.get_group(Matcher(NPCComponent)).entities:
            if entity.get(NPCComponent).current_stage == stage:
                npcs.append(entity.get(NPCComponent))
        return npcs