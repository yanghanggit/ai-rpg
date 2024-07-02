from overrides import override
from entitas import Entity, Matcher, InitializeProcessor, ExecuteProcessor # type: ignore
from ecs_systems.components import WorldComponent, StageComponent, ActorComponent, \
    PlayerComponent, PerceptionActionComponent, CheckStatusActionComponent
from builtin_prompt.cn_builtin_prompt import (kick_off_memory_actor_prompt, kick_off_memory_stage_prompt, kick_off_world_system_prompt)
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from typing import Dict, Set
from my_agent.agent_action import AgentAction

###############################################################################################################################################
class AgentsKickOffSystem(InitializeProcessor, ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
        self.tasks: Dict[str, str] = {}
        self._once_add_perception_and_check_status: bool = False
###############################################################################################################################################
    @override
    def initialize(self) -> None:
        #分段处理
        self.tasks.clear()
        world_tasks = self.create_world_system_tasks()
        stage_tasks = self.create_stage_tasks()
        actor_tasks = self.create_actor_tasks()
        #填进去
        self.tasks.update(world_tasks)
        self.tasks.update(stage_tasks)
        self.tasks.update(actor_tasks)
###############################################################################################################################################
    @override
    def execute(self) -> None:
        if not self._once_add_perception_and_check_status:
            self.once_add_perception_and_check_status()
            self._once_add_perception_and_check_status = True
####################################################################################################
    def once_add_perception_and_check_status(self) -> None:
        context = self.context
        entities: Set[Entity] = context.get_group(Matcher(all_of=[ActorComponent], none_of=[PlayerComponent])).entities
        for entity in entities:
            actor_name: ActorComponent = entity.get(ActorComponent)
            #
            if not entity.has(PerceptionActionComponent):
                perception_action = AgentAction(actor_name.name, PerceptionActionComponent.__name__, [actor_name.current_stage])
                entity.add(PerceptionActionComponent, perception_action)
            #
            if not entity.has(CheckStatusActionComponent):
                check_status_action = AgentAction(actor_name.name, CheckStatusActionComponent.__name__, [actor_name.name])
                entity.add(CheckStatusActionComponent, check_status_action)
####################################################################################################
    @override
    async def async_pre_execute(self) -> None:
        context = self.context
        agent_connect_system = context._langserve_agent_system
        if len(self.tasks) == 0:
            return
        
        for name, prompt in self.tasks.items():
            agent_connect_system.add_request_task(name, prompt)

        await context._langserve_agent_system.request_tasks("AgentsKickOffSystem")
        self.tasks.clear() # 这句必须得走.
###############################################################################################################################################
    def create_world_system_tasks(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        #
        context = self.context
        worlds: Set[Entity] = context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            
            worldcomp: WorldComponent = world.get(WorldComponent)
            prompt = kick_off_world_system_prompt()
            result[worldcomp.name] = prompt
        
        return result
###############################################################################################################################################
    def create_stage_tasks(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        #
        context = self.context
        memory_system = context._kick_off_memory_system
        stages: Set[Entity] = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:

            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.get_kick_off_memory(stagecomp.name)
            if stagememory == "":
                logger.error(f"stagememory is empty: {stagecomp.name}")
                continue

            prompt = kick_off_memory_stage_prompt(stagememory)
            result[stagecomp.name] = prompt
        
        return result
###############################################################################################################################################
    def create_actor_tasks(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        #
        context = self.context
        memory_system = context._kick_off_memory_system
        actor_entities: Set[Entity] = context.get_group(Matcher(all_of=[ActorComponent])).entities
        for _entity in actor_entities:

            actor_comp: ActorComponent = _entity.get(ActorComponent)
            _name: str = actor_comp.name
            
            _kick_off_memory = memory_system.get_kick_off_memory(_name)
            if _kick_off_memory == "":
                logger.error(f"_kick_off_memory is empty: {_name}")
                continue
            
            prompt = kick_off_memory_actor_prompt(_kick_off_memory)
            result[_name] = prompt

        return result
###############################################################################################################################################
