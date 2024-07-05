from overrides import override
from entitas import Entity, Matcher, InitializeProcessor, ExecuteProcessor # type: ignore
from ecs_systems.components import WorldComponent, StageComponent, ActorComponent, \
    PlayerComponent, PerceptionActionComponent, CheckStatusActionComponent
from builtin_prompt.cn_builtin_prompt import (kick_off_memory_actor_prompt, kick_off_memory_stage_prompt, kick_off_world_system_prompt)
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from typing import Dict, Set
from my_agent.agent_action import AgentAction
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask, LangServeAgentAsyncRequestTasksGather

###############################################################################################################################################
class AgentsKickOffSystem(InitializeProcessor, ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self._context: ExtendedContext = context
        self._request_tasks: Dict[str, LangServeAgentRequestTask] = {}
        self._once_add_perception_and_check_status: bool = False
###############################################################################################################################################
    @override
    def initialize(self) -> None:
        #分段处理
        self._request_tasks.clear()
        world_tasks = self.create_world_system_tasks()
        stage_tasks = self.create_stage_tasks()
        actor_tasks = self.create_actor_tasks()
        #填进去
        self._request_tasks.update(world_tasks)
        self._request_tasks.update(stage_tasks)
        self._request_tasks.update(actor_tasks)
###############################################################################################################################################
    @override
    def execute(self) -> None:
        if not self._once_add_perception_and_check_status:
            self.once_add_perception_and_check_status()
            self._once_add_perception_and_check_status = True
####################################################################################################
    def once_add_perception_and_check_status(self) -> None:
        context = self._context
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
        if len(self._request_tasks) == 0:
            return

        tasks_gather = LangServeAgentAsyncRequestTasksGather("AgentsKickOffSystem Gather", self._request_tasks)
        request_result = await tasks_gather.gather()
        if len(request_result) == 0:
            logger.warning(f"ActorPlanningSystem: request_result is empty.")
            return

        self._request_tasks.clear() # 这句必须得走.
###############################################################################################################################################
    def create_world_system_tasks(self) -> Dict[str, LangServeAgentRequestTask]:
        result: Dict[str, LangServeAgentRequestTask] = {}
    
        world_entities: Set[Entity] = self._context.get_group(Matcher(WorldComponent)).entities
        for world_entity in world_entities:
            world_comp = world_entity.get(WorldComponent)
            prompt = kick_off_world_system_prompt()
            task = self._context._langserve_agent_system.create_agent_request_task(world_comp.name, prompt)
            assert task is not None, f"task is None: {world_comp.name}"
            if task is not None:
                result[world_comp.name] = task
        
        return result
###############################################################################################################################################
    def create_stage_tasks(self) -> Dict[str, LangServeAgentRequestTask]:
        result: Dict[str, LangServeAgentRequestTask] = {}
       
        stage_entities: Set[Entity] = self._context.get_group(Matcher(StageComponent)).entities
        for stage_entity in stage_entities:

            stage_comp = stage_entity.get(StageComponent)
            kick_off_memory = self._context._kick_off_memory_system.get_kick_off_memory(stage_comp.name)
            if kick_off_memory == "":
                logger.error(f"stagememory is empty: {stage_comp.name}")
                continue

            prompt = kick_off_memory_stage_prompt(kick_off_memory)
            task = self._context._langserve_agent_system.create_agent_request_task(stage_comp.name, prompt)
            assert task is not None, f"task is None: {stage_comp.name}"
            if task is not None:
                result[stage_comp.name] = task
        
        return result
###############################################################################################################################################
    def create_actor_tasks(self) -> Dict[str, LangServeAgentRequestTask]:
        result: Dict[str, LangServeAgentRequestTask] = {}
     
        actor_entities: Set[Entity] = self._context.get_group(Matcher(all_of=[ActorComponent])).entities
        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            kick_off_memory = self._context._kick_off_memory_system.get_kick_off_memory(actor_comp.name)
            if kick_off_memory == "":
                logger.error(f"_kick_off_memory is empty: {actor_comp.name}")
                continue
            
            prompt = kick_off_memory_actor_prompt(kick_off_memory)
            task = self._context._langserve_agent_system.create_agent_request_task(actor_comp.name, prompt)
            assert task is not None, f"task is None: {actor_comp.name}"
            if task is not None:
                result[actor_comp.name] = task
           
        return result
###############################################################################################################################################
