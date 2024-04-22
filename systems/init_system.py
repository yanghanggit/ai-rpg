from entitas import Entity, Matcher, InitializeProcessor # type: ignore
from auxiliary.components import WorldComponent, StageComponent, NPCComponent, PlayerComponent
from auxiliary.prompt_maker import read_archives_when_system_init_prompt
from auxiliary.extended_context import ExtendedContext
from loguru import logger


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

        ##连接所有的agent
        self.connect_agents()
        
        ##初始化所有的记忆
        self.read_agent_memory()
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
    def connect_agents(self) -> None:
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
    def read_agent_memory(self) -> None:
        #
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system
        chaos_engineering_system = context.chaos_engineering_system
        #
        worlds: set[Entity] = context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            worldmemory = memory_system.getmemory(worldcomp.name)
            if worldmemory == "":
                logger.error(f"worldmemory is empty: {worldcomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(worldmemory, world, context)
            # response = agent_connect_system.request(worldcomp.name, readarchprompt)
            # if response is None:
            #     chaos_engineering_system.on_read_memory_failed(context, worldcomp.name, readarchprompt)
            agent_connect_system.add_async_requet_task(worldcomp.name, readarchprompt)

        ##
        stages: set[Entity] = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.getmemory(stagecomp.name)
            if stagememory == "":
                logger.error(f"stagememory is empty: {stagecomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(stagememory, stage, context)
            # response = agent_connect_system.request(stagecomp.name, readarchprompt)
            # if response is None:
            #     chaos_engineering_system.on_read_memory_failed(context, stagecomp.name, readarchprompt)
            agent_connect_system.add_async_requet_task(stagecomp.name, readarchprompt)

        ##
        npcs: set[Entity] = context.get_group(Matcher(all_of=[NPCComponent], none_of=[PlayerComponent])).entities
        for npc in npcs:
            npccomp: NPCComponent = npc.get(NPCComponent)
            npcmemory = memory_system.getmemory(npccomp.name)
            if npcmemory == "":
                logger.error(f"npcmemory is empty: {npccomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(npcmemory, npc, context)
            # response = agent_connect_system.request(npccomp.name, readarchprompt)
            # if response is None:
            #     chaos_engineering_system.on_read_memory_failed(context, npccomp.name, readarchprompt)
            agent_connect_system.add_async_requet_task(npccomp.name, readarchprompt)

        ##
        agent_connect_system.run_async_requet_tasks()

###############################################################################################################################################