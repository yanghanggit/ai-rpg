from typing import override
from entitas import Entity, Matcher, InitializeProcessor # type: ignore
from auxiliary.components import WorldComponent, StageComponent, ActorComponent, PlayerComponent
from auxiliary.extended_context import ExtendedContext


# 远程连接agent
class AgentsConnectSystem(InitializeProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
###############################################################################################################################################
    @override
    def initialize(self) -> None:
        self.connect_world_agents()
        self.connect_stage_agents()
        self.connect_actor_agents()
###############################################################################################################################################
    def connect_world_agents(self) -> None:
        agent_connect_system = self.context.agent_connect_system
        worlds: set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            agent_connect_system.connect_agent(worldcomp.name)
###############################################################################################################################################
    def connect_stage_agents(self) -> None:
        agent_connect_system = self.context.agent_connect_system
        stages: set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            agent_connect_system.connect_agent(stagecomp.name)
###############################################################################################################################################
    def connect_actor_agents(self) -> None:
        agent_connect_system = self.context.agent_connect_system
        npcs: set[Entity] = self.context.get_group(Matcher(all_of=[ActorComponent], none_of=[PlayerComponent])).entities
        for npc in npcs:
            npccomp: ActorComponent = npc.get(ActorComponent)
            agent_connect_system.connect_agent(npccomp.name)
###############################################################################################################################################
    