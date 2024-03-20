
from entitas import Entity, Matcher, Context, InitializeProcessor # type: ignore
from auxiliary.components import WorldComponent, StageComponent, NPCComponent, PlayerComponent
from agents.tools.extract_md_content import extract_md_content
from auxiliary.actor_agent import ActorAgent
from auxiliary.prompt_maker import read_archives_when_system_init_prompt
from auxiliary.extended_context import ExtendedContext
from loguru import logger # type: ignore


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class InitSystem(InitializeProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
      
    def initialize(self) -> None:
        logger.debug("<<<<<<<<<<<<<  InitSystem >>>>>>>>>>>>>>>>>")
        self.handleworld()
        self.handlestages()
        self.handlenpcs()

    def handleworld(self) -> None:
        worlds: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            comp: WorldComponent = world.get(WorldComponent)
            # 世界载入
            agent: ActorAgent = comp.agent
            logger.debug(f"NPC: {comp.name}, Agent: {agent.url}, Memory: {comp.agent.memory}")
            agent.connect()

            init_archivist = extract_md_content(agent.memory)
            prompt = read_archives_when_system_init_prompt(init_archivist, world, self.context)
            comp.agent.request(prompt)
        
    def handlestages(self) -> None:
        stages: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            comp: StageComponent = stage.get(StageComponent)
            # 场景载入
            agent: ActorAgent = comp.agent
            logger.debug(f"NPC: {comp.name}, Agent: {agent.url}, Memory: {comp.agent.memory}")
            agent.connect()
            
            init_archivist = extract_md_content(agent.memory)
            prompt = read_archives_when_system_init_prompt(init_archivist, stage, self.context)
            comp.agent.request(prompt)

    def handlenpcs(self) -> None:
        npcs: set[Entity] = self.context.get_group(Matcher(NPCComponent)).entities
        for npc in npcs:
            comp: NPCComponent = npc.get(NPCComponent)
            # NPC载入
            agent: ActorAgent = comp.agent
            logger.debug(f"NPC: {comp.name}, Agent: {agent.url}, Memory: {comp.agent.memory}")
            agent.connect()

            init_archivist = extract_md_content(agent.memory)
            prompt = read_archives_when_system_init_prompt(init_archivist, npc, self.context)
            comp.agent.request(prompt)
