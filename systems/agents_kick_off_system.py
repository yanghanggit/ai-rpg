from overrides import override
from entitas import Entity, Matcher, InitializeProcessor, ExecuteProcessor # type: ignore
from auxiliary.components import WorldComponent, StageComponent, ActorComponent, PlayerComponent, PerceptionActionComponent, CheckStatusActionComponent
from auxiliary.cn_builtin_prompt import (kick_off_memory_actor_prompt, kick_off_memory_stage_prompt)
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from systems.update_archive_helper import UpdareArchiveHelper
from typing import Dict
from auxiliary.actor_plan_and_action import ActorAction

###############################################################################################################################################
class AgentsKickOffSystem(InitializeProcessor, ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
        self.tasks: Dict[str, str] = {}
        self.flag_first_time_add_perception_and_check_status: bool = False
###############################################################################################################################################
    @override
    def initialize(self) -> None:
        context = self.context
        helper = UpdareArchiveHelper(context)
        helper.prepare()
        #分段处理
        self.tasks.clear()
        world_tasks = self.create_world_tasks(helper)
        stage_tasks = self.create_stage_tasks(helper)
        actor_tasks = self.create_actor_tasks(helper)
        #填进去
        self.tasks.update(world_tasks)
        self.tasks.update(stage_tasks)
        self.tasks.update(actor_tasks)
###############################################################################################################################################
    @override
    def execute(self) -> None:
        if not self.flag_first_time_add_perception_and_check_status:
            self.first_time_add_perception_and_check_status()
            self.flag_first_time_add_perception_and_check_status = True
####################################################################################################
    def first_time_add_perception_and_check_status(self) -> None:
        context = self.context
        entities: set[Entity] = context.get_group(Matcher(all_of=[ActorComponent], none_of=[PlayerComponent])).entities
        for entity in entities:
            actor_name: ActorComponent = entity.get(ActorComponent)
            #
            if not entity.has(PerceptionActionComponent):
                perception_action = ActorAction(actor_name.name, PerceptionActionComponent.__name__, [actor_name.current_stage])
                entity.add(PerceptionActionComponent, perception_action)
            #
            if not entity.has(CheckStatusActionComponent):
                check_status_action = ActorAction(actor_name.name, CheckStatusActionComponent.__name__, [actor_name.name])
                entity.add(CheckStatusActionComponent, check_status_action)
####################################################################################################
    @override
    async def async_pre_execute(self) -> None:
        context = self.context
        agent_connect_system = context.agent_connect_system
        if len(self.tasks) == 0:
            #logger.error("InitMemorySystem tasks is empty.")
            return
        
        for name, prompt in self.tasks.items():
            agent_connect_system.add_async_request_task(name, prompt)

        await context.agent_connect_system.run_async_requet_tasks("InitMemorySystem")
        self.tasks.clear() # 这句必须得走！！！
        logger.info("InitMemorySystem done.")
###############################################################################################################################################
    def create_world_tasks(self, helper: UpdareArchiveHelper) -> Dict[str, str]:

        result: Dict[str, str] = {}

        context = self.context
        memory_system = context.kick_off_memory_system
        agent_connect_system = context.agent_connect_system
        worlds: set[Entity] = context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            worldmemory = memory_system.get_kick_off_memory(worldcomp.name)
            if worldmemory == "":
                logger.error(f"worldmemory is empty: {worldcomp.name}")
                continue
            prompt = kick_off_memory_actor_prompt(worldmemory)
            agent_connect_system.add_async_request_task(worldcomp.name, prompt)
            result[worldcomp.name] = prompt
        
        return result
###############################################################################################################################################
    def create_stage_tasks(self, helper: UpdareArchiveHelper) -> Dict[str, str]:

        result: Dict[str, str] = {}

        context = self.context
        memory_system = context.kick_off_memory_system
        agent_connect_system = context.agent_connect_system
        stages: set[Entity] = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:

            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.get_kick_off_memory(stagecomp.name)
            if stagememory == "":
                logger.error(f"stagememory is empty: {stagecomp.name}")
                continue

            prompt = kick_off_memory_stage_prompt(stagememory)
            agent_connect_system.add_async_request_task(stagecomp.name, prompt)
            result[stagecomp.name] = prompt
        
        return result
###############################################################################################################################################
    def create_actor_tasks(self, helper: UpdareArchiveHelper) -> Dict[str, str]:

        result: Dict[str, str] = {}

        #
        context = self.context
        memory_system = context.kick_off_memory_system
        agent_connect_system = context.agent_connect_system
        actor_entities: set[Entity] = context.get_group(Matcher(all_of=[ActorComponent])).entities
        for _entity in actor_entities:
            actor_comp: ActorComponent = _entity.get(ActorComponent)
            _name: str = actor_comp.name
            _kick_off_memory = memory_system.get_kick_off_memory(_name)
            if _kick_off_memory == "":
                logger.error(f"_kick_off_memory is empty: {_name}")
                continue
            prompt = kick_off_memory_actor_prompt(_kick_off_memory)
            agent_connect_system.add_async_request_task(_name, prompt)
            result[_name] = prompt

        return result
###############################################################################################################################################
