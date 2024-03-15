
from entitas import Matcher, Context, InitializeProcessor
from components import WorldComponent, StageComponent, NPCComponent
from agents.tools.extract_md_content import extract_md_content
from actor_agent import ActorAgent
from prompt_maker import read_archives_when_system_init_prompt

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
            prompt = read_archives_when_system_init_prompt(init_archivist, world, self.context)
            comp.agent.request(prompt)
        
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
            prompt = read_archives_when_system_init_prompt(init_archivist, stage, self.context)
            comp.agent.request(prompt)

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
            prompt = read_archives_when_system_init_prompt(init_archivist, npc, self.context)
            comp.agent.request(prompt)
