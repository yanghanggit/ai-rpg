from typing import override, Set
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
        self.connect_world_system_agents()
        self.connect_stage_agents()
        self.connect_actor_agents()
###############################################################################################################################################
    def connect_world_system_agents(self) -> None:
        agent_connect_system = self.context.agent_connect_system
        worlds: Set[Entity] = self.context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            agent_connect_system.connect_agent(worldcomp.name)
###############################################################################################################################################
    def connect_stage_agents(self) -> None:
        agent_connect_system = self.context.agent_connect_system
        stages: Set[Entity] = self.context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            agent_connect_system.connect_agent(stagecomp.name)
###############################################################################################################################################
    def connect_actor_agents(self) -> None:
        agent_connect_system = self.context.agent_connect_system
        actors: Set[Entity] = self.context.get_group(Matcher(all_of=[ActorComponent], none_of=[PlayerComponent])).entities
        for _entity in actors:
            actor_comp: ActorComponent = _entity.get(ActorComponent)
            agent_connect_system.connect_agent(actor_comp.name)
###############################################################################################################################################
    