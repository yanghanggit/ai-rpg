
from entitas import Matcher, Context, InitializeProcessor
from components import WorldComponent, StageComponent, NPCComponent
from agents.tools.extract_md_content import extract_md_content
from actor_agent import ActorAgent

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
            comp: WorldComponent = world.get(WorldComponent)
            print(comp.name)
            print(comp.agent)
            print(comp.agent.memory)
            # 世界载入
            agent: ActorAgent = comp.agent
            agent.connect()
            if agent.memory == "":
                agent.memory = "/savedData/basic_archive.md"
                print(f"{agent.name}未找到专属存档，载入默认存档")

            init_archivist = extract_md_content(agent.memory)
            load_prompt = f"""
# 你需要恢复记忆
## 步骤:
- 第1步:记忆如下{init_archivist}.
- 第2步:理解其中所有的信息.
- 第3步:理解其中关于你的信息（如果提到了你，那就是关于你的信息.）
- 第4步:根据信息更新你的最新状态与逻辑.
## 输出规则：
- 保留关键信息(时间，地点，人物，事件)，不要推断，增加与润色。
- 输出在保证语意完整基础上字符尽量少。
"""
            # print(f"{comp.name}读取存档记忆=>\n{load_prompt}")
            loadres = comp.agent.request(load_prompt)

            #print(f"[{comp.name}]load=>", loadres)
            # print("______________________________________")
        
    def handlestages(self) -> None:
        stages: set = self.context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            comp: StageComponent = stage.get(StageComponent)
            print(comp.name)
            print(comp.agent)
            print(comp.agent.memory)
            # 场景载入
            agent: ActorAgent = comp.agent
            agent.connect()
            if agent.memory == "":
                agent.memory = "/savedData/basic_archive.md" 
                print(f"{agent.name}未找到专属存档，载入默认存档")
            
            init_archivist = extract_md_content(agent.memory)
            load_prompt = f"""
# 你需要恢复记忆
## 步骤:
- 第1步:记忆如下{init_archivist}.
- 第2步:理解其中所有的信息.
- 第3步:理解其中关于你的信息（如果提到了你，那就是关于你的信息.）
- 第4步:根据信息更新你的最新状态与逻辑.
## 输出规则：
- 保留关键信息(时间，地点，人物，事件)，不要推断，增加与润色。
- 输出在保证语意完整基础上字符尽量少。
"""
            # print(f"{comp.name}读取存档记忆=>\n{load_prompt}")
            loadres = comp.agent.request(load_prompt)
            
            #print(f"[{comp.name}]load=>", loadres)
            # print("______________________________________")

    def handlenpcs(self) -> None:
        npcs: set = self.context.get_group(Matcher(NPCComponent)).entities
        for npc in npcs:
            comp: NPCComponent = npc.get(NPCComponent)
            print(comp.name)
            print(comp.agent)
            print(comp.agent.memory)
            # NPC载入
            agent: ActorAgent = comp.agent
            agent.connect()
            if agent.memory == "":
                agent.memory = "/savedData/basic_archive.md" 
                print(f"{agent.name}未找到专属存档，载入默认存档")

            init_archivist = extract_md_content(agent.memory)
            load_prompt = f"""
# 你需要恢复记忆
## 步骤:
- 第1步:记忆如下{init_archivist}.
- 第2步:理解其中所有的信息.
- 第3步:理解其中关于你的信息（如果提到了你，那就是关于你的信息.）
- 第4步:根据信息更新你的最新状态与逻辑.
## 输出规则：
- 保留关键信息(时间，地点，人物，事件)，不要推断，增加与润色。
- 输出在保证语意完整基础上字符尽量少。
"""
            # print(f"{comp.name}读取存档记忆=>\n{load_prompt}")
            loadres = comp.agent.request(load_prompt)
            
            #print(f"[{comp.name}]load=>", loadres)
            # print("______________________________________")