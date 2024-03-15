
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent
from components import WhisperActionComponent, StageComponent, NPCComponent
from actor_action import ActorAction
from extended_context import ExtendedContext
from agents.tools.print_in_color import Color

class WhisperActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(WhisperActionComponent): GroupEvent.ADDED}

    def filter(self, entity: list[Entity]):
        return entity.has(WhisperActionComponent)

    def react(self, entities: list[Entity]):
        print("<<<<<<<<<<<<<  WhisperActionSystem  >>>>>>>>>>>>>>>>>")

        for entity in entities:
            self.handle(entity)  # 核心处理

        for entity in entities:
            entity.remove(WhisperActionComponent)  # 必须移除！！！       

    def handle(self, entity: Entity) -> None:

        whispercomp: WhisperActionComponent = entity.get(WhisperActionComponent)
        stagecomp: StageComponent = self.context.get_stagecomponent_by_uncertain_entity(entity) 
        if stagecomp is None or whispercomp is None:
            print(f"WhisperActionSystem: stagecomp or whispercomp is None!")
            return
        

#         <<<<<<<<<<<<<  MindVoiceActionSystem  >>>>>>>>>>>>>>>>>
# 无影,心里想到:我记得在悠扬林谷中到处溜达，寻找偷取的目标。
# 坏运气先生,心里想到:我在老猎人的小屋里找到了一些食物。我需要避免被‘卡斯帕·艾伦德’和他的小狗‘断剑’发现。
# 卡斯帕·艾伦德,心里想到:可能是时候再次出发，寻找一些新的冒险了。
# 悠扬林谷,心里想到:我记得那个被称为'无影'的小偷正在我的林谷中溜达，寻找偷取的目标。
# 老猎人隐居的小木屋,心里想到:我是卡斯帕·艾伦德的小木屋，位于悠扬林谷深处。
# 断剑,心里想到:我记得了，我是断剑，卡斯帕的忠诚小狗。现在在屋子里一角睡觉。
# <<<<<<<<<<<<<  WhisperActionSystem  >>>>>>>>>>>>>>>>>
# 悠扬林谷 密语到 :卡斯帕·艾伦德
# 悠扬林谷 密语到 :有个小偷名叫'无影'在林子里，要小心。

        #debug!
        action: ActorAction = whispercomp.action
        for value in action.values:
            print(f"{Color.HEADER}{action.name} 密语到 :{value}{Color.ENDC}")


        values: list[str] = action.values
        if len(values) < 2:
            return

        target_name: str = values[0]
        target_entity = self.context.getnpc(target_name)
        if target_entity is None:
            print(f"要低语的对象不存在")
            return
        
        target_npc_comp: NPCComponent = target_entity.get(NPCComponent)
        if target_npc_comp.current_stage != stagecomp.name:
            print(f"不在本场景里！")
            return
        
        #组装新的记忆。但是不要加到场景事件里
        content: str = values[1]
        new_memory = f"{action.name}对{target_name}低语道:{content}"

        ###加到发起者和接受者的记忆里
        if entity.has(NPCComponent):
            entity.get(NPCComponent).agent.add_chat_history(new_memory)
        elif entity.has(StageComponent):
            entity.get(StageComponent).agent.add_chat_history(new_memory)

        ### 接受对话的只能是npc
        target_entity.get(NPCComponent).agent.add_chat_history(new_memory)

            
        
                