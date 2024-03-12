
from entitas import Matcher, Context, InitializeProcessor
from components import WorldComponent, StageComponent, NPCComponent

#
init_archivist = f"""
# 游戏世界存档
- 大陆纪元2000年1月1日，冬夜.
- 温斯洛平原的深处的“悠扬林谷”中的“老猎人隐居的小木屋”里。
- “卡斯帕·艾伦德”坐在他的“老猎人隐居的小木屋”中的壁炉旁，在沉思和回忆过往，并向壁炉中的火投入了一根木柴。
- 他的小狗（名叫"断剑"）在屋子里的一角睡觉。
- 一只老鼠（名叫"坏运气先生"）在屋子里的另一角找到了一些食物。
"""
load_prompt = f"""
# 你需要读取存档
## 步骤:
- 第1步，读取{init_archivist}.
- 第2步：理解其中所有的信息
- 第3步：理解其中关于你的信息（如何提到了你，那就是你）
- 第3步：根据信息更新你的最新状态与逻辑.
## 输出规则：
- 保留关键信息(时间，地点，人物，事件)，不要推断，增加与润色。输出在保证语意完整基础上字符尽量少。
"""



###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class InitSystem(InitializeProcessor):

    def __init__(self, context: Context) -> None:
        self.context: Context = context
      
    def initialize(self) -> None:
        print("<<<<<<<<<<<<<  InitSystem >>>>>>>>>>>>>>>>>")
        self.handleworld()
        self.handlestages()
        self.handlenpcs()

    def handleworld(self) -> None:
        worlds: set = self.context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            comp = world.get(WorldComponent)
            print(comp.name)
            print(comp.agent)
            # 世界载入
            comp.agent.connect()
            loadres = comp.agent.request(load_prompt)

            #print(f"[{comp.name}]load=>", loadres)
            print("______________________________________")
        
    def handlestages(self) -> None:
        stages: set = self.context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            comp = stage.get(StageComponent)
            print(comp.name)
            print(comp.agent)
            # 场景载入
            comp.agent.connect()
            loadres = comp.agent.request(load_prompt)
            
            #print(f"[{comp.name}]load=>", loadres)
            print("______________________________________")

    def handlenpcs(self) -> None:
        npcs: set = self.context.get_group(Matcher(NPCComponent)).entities
        for npc in npcs:
            comp = npc.get(NPCComponent)
            print(comp.name)
            print(comp.agent)
            # NPC载入
            comp.agent.connect()
            loadres = comp.agent.request(load_prompt)
            
            #print(f"[{comp.name}]load=>", loadres)
            print("______________________________________")