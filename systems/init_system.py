
from typing import Optional
from entitas import Entity, Matcher, InitializeProcessor # type: ignore
from auxiliary.components import WorldComponent, StageComponent, NPCComponent, PlayerComponent
from auxiliary.extract_md_content import extract_md_content
from auxiliary.actor_agent import ActorAgent
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
      
    def initialize(self) -> None:
        logger.debug("<<<<<<<<<<<<<  InitSystem  >>>>>>>>>>>>>>>>>")
        # self.handleworld()
        # self.handlestages()
        # self.handlenpcs()

        ##
        self.context.memory_system.debug_show_all_memory()

        ####
        self.handle_connect_all_agents()
        self.handle_init_memories()
        self.handle_init_files()

    def handle_connect_all_agents(self) -> None:
        pass

    def handle_init_memories(self) -> None:
        pass

    def handle_init_files(self) -> None:
        pass

    def handleworld(self) -> None:
        worlds: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            # 世界载入
            agent: ActorAgent = worldcomp.agent
            logger.debug(f"NPC: {worldcomp.name}, Agent: {agent.url}, Memory: {agent.read_memory_path}")
            agent.connect()
            readarchprompt = read_archives_when_system_init_prompt(agent.read_memory_path, world, self.context)
            agent.request(readarchprompt)
        
    def handlestages(self) -> None:
        stages: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            # 场景载入
            agent: ActorAgent = stagecomp.agent
            logger.debug(f"NPC: {stagecomp.name}, Agent: {agent.url}, Memory: {agent.read_memory_path}")
            agent.connect()
            readarchprompt = read_archives_when_system_init_prompt(agent.read_memory_path, stage, self.context)
            agent.request(readarchprompt)

    def handlenpcs(self) -> None:
        # 如果是PlayerComponent控制的entity，就不要connect
        npcs: set[Entity] = self.context.get_group(Matcher(all_of=[NPCComponent], none_of=[PlayerComponent])).entities
        for npc in npcs:
            npccomp: NPCComponent = npc.get(NPCComponent)
            # entity: Optional[Entity] = self.context.get_entity_by_name(comp.name)
            # if entity is not None and entity.has(PlayerComponent):
            #     logger.debug(f"NPC: {comp.name} is a player, skip loading memmory.")
            #     continue
            # NPC载入
            agent: ActorAgent = npccomp.agent
            logger.debug(f"NPC: {npccomp.name}, Agent: {agent.url}, Memory: {agent.read_memory_path}")
            agent.connect()
            readarchprompt = read_archives_when_system_init_prompt(agent.read_memory_path, npc, self.context)
            agent.request(readarchprompt)
