from typing import override, Set
from entitas import Entity, Matcher, InitializeProcessor # type: ignore
from ecs_systems.components import WorldComponent, StageComponent, ActorComponent, PlayerComponent
from my_entitas.extended_context import ExtendedContext


# 远程连接agent
class AgentsConnectSystem(InitializeProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self._context: ExtendedContext = context
###############################################################################################################################################
    @override
    def initialize(self) -> None:
        self.connect_world_system_agents()
        self.connect_stage_agents()
        self.connect_actor_agents()
###############################################################################################################################################
    def connect_world_system_agents(self) -> None:
        world_entities: Set[Entity] = self._context.get_group(Matcher(WorldComponent)).entities
        for world_entity in world_entities:
            world_comp = world_entity.get(WorldComponent)
            self._context._langserve_agent_system.connect_agent(world_comp.name)
###############################################################################################################################################
    def connect_stage_agents(self) -> None:
        stage_entities: Set[Entity] = self._context.get_group(Matcher(StageComponent)).entities
        for stage_entity in stage_entities:
            stage_comp = stage_entity.get(StageComponent)
            self._context._langserve_agent_system.connect_agent(stage_comp.name)
###############################################################################################################################################
    def connect_actor_agents(self) -> None:
        actor_entities: Set[Entity] = self._context.get_group(Matcher(all_of = [ActorComponent], none_of = [PlayerComponent])).entities
        for actor_entity in actor_entities:
            actor_comp = actor_entity.get(ActorComponent)
            self._context._langserve_agent_system.connect_agent(actor_comp.name)
###############################################################################################################################################
    