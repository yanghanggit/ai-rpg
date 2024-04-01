
from typing import Optional
from entitas import Entity, Matcher, InitializeProcessor # type: ignore
from auxiliary.components import WorldComponent, StageComponent, NPCComponent, PlayerComponent
from auxiliary.extract_md_content import extract_md_content
from auxiliary.actor_agent import ActorAgent
from auxiliary.prompt_maker import read_archives_when_system_init_prompt
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.memory_system import MemorySystem


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class InitSystem(InitializeProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
      
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
    def initialize(self) -> None:
        logger.debug("<<<<<<<<<<<<<  InitSystem  >>>>>>>>>>>>>>>>>")
        # self.handleworld()
        # self.handlestages()
        # self.handlenpcs()

        ##debug
        #self.context.agent_connect_system.debug_show_all_agents()
        #self.context.memory_system.debug_show_all_memory()

        ##连接所有的agent
        self.handle_connect_all_agents()
        ##初始化所有的记忆
        self.handle_init_memories()
        ##初始化所有的文件
        self.handle_init_files()
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
    def handle_connect_all_agents(self) -> None:
        #
        agent_connect_system = self.context.agent_connect_system
        #
        worlds: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            agent_connect_system.connect_actor_agent(worldcomp.name)

        stages: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            agent_connect_system.connect_actor_agent(stagecomp.name)

        npcs: set[Entity] = self.context.get_group(Matcher(all_of=[NPCComponent], none_of=[PlayerComponent])).entities
        for npc in npcs:
            npccomp: NPCComponent = npc.get(NPCComponent)
            agent_connect_system.connect_actor_agent(npccomp.name)
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
    def handle_init_memories(self) -> None:
        #
        memory_system = self.context.memory_system
        agent_connect_system = self.context.agent_connect_system
        #
        worlds: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            worldmemory = memory_system.getmemory(worldcomp.name)
            readarchprompt = read_archives_when_system_init_prompt(worldmemory, world, self.context)
            agent_connect_system.request2(worldcomp.name, readarchprompt)
        ##
        stages: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.getmemory(stagecomp.name)
            readarchprompt = read_archives_when_system_init_prompt(stagememory, stage, self.context)
            agent_connect_system.request2(stagecomp.name, readarchprompt)

        ##
        npcs: set[Entity] = self.context.get_group(Matcher(all_of=[NPCComponent], none_of=[PlayerComponent])).entities
        for npc in npcs:
            npccomp: NPCComponent = npc.get(NPCComponent)
            npcmemory = memory_system.getmemory(npccomp.name)
            readarchprompt = read_archives_when_system_init_prompt(npcmemory, npc, self.context)
            agent_connect_system.request2(npccomp.name, readarchprompt)
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
    def handle_init_files(self) -> None:
        pass

    # def handleworld(self) -> None:
    #     worlds: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
    #     for world in worlds:
    #         worldcomp: WorldComponent = world.get(WorldComponent)
    #         # 世界载入
    #         agent: ActorAgent = worldcomp.agent
    #         logger.debug(f"NPC: {worldcomp.name}, Agent: {agent.url}, Memory: {agent.read_memory_path}")
    #         agent.connect()
    #         readarchprompt = read_archives_when_system_init_prompt(agent.read_memory_path, world, self.context)
    #         agent.request(readarchprompt)
        
    # def handlestages(self) -> None:
    #     stages: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
    #     for stage in stages:
    #         stagecomp: StageComponent = stage.get(StageComponent)
    #         # 场景载入
    #         agent: ActorAgent = stagecomp.agent
    #         logger.debug(f"NPC: {stagecomp.name}, Agent: {agent.url}, Memory: {agent.read_memory_path}")
    #         agent.connect()
    #         readarchprompt = read_archives_when_system_init_prompt(agent.read_memory_path, stage, self.context)
    #         agent.request(readarchprompt)

    # def handlenpcs(self) -> None:
    #     # 如果是PlayerComponent控制的entity，就不要connect
    #     npcs: set[Entity] = self.context.get_group(Matcher(all_of=[NPCComponent], none_of=[PlayerComponent])).entities
    #     for npc in npcs:
    #         npccomp: NPCComponent = npc.get(NPCComponent)
    #         # entity: Optional[Entity] = self.context.get_entity_by_name(comp.name)
    #         # if entity is not None and entity.has(PlayerComponent):
    #         #     logger.debug(f"NPC: {comp.name} is a player, skip loading memmory.")
    #         #     continue
    #         # NPC载入
    #         agent: ActorAgent = npccomp.agent
    #         logger.debug(f"NPC: {npccomp.name}, Agent: {agent.url}, Memory: {agent.read_memory_path}")
    #         agent.connect()
    #         readarchprompt = read_archives_when_system_init_prompt(agent.read_memory_path, npc, self.context)
    #         agent.request(readarchprompt)
