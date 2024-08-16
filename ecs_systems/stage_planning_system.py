from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from overrides import override
from ecs_systems.components import (StageComponent, AutoPlanningComponent, ActorComponent)
from ecs_systems.action_components import STAGE_AVAILABLE_ACTIONS_REGISTER, STAGE_CONVERSATION_ACTIONS_REGISTER
from my_agent.agent_plan import AgentPlan
from my_agent.agent_action import AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger 
from typing import Dict, Set, List
from gameplay_checks.planning_check import check_component_register
from file_system.files_def import PropFile
import ecs_systems.cn_builtin_prompt as builtin_prompt
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask, LangServeAgentAsyncRequestTasksGather

#######################################################################################################################################
class StagePlanningSystem(ExecuteProcessor):

    """
    场景计划系统
    """

    def __init__(self, context: RPGEntitasContext) -> None:
        self._context = context
        self._tasks: Dict[str, LangServeAgentRequestTask] = {}
#######################################################################################################################################
    @override
    def execute(self) -> None:
        pass
#######################################################################################################################################
    @override
    async def async_pre_execute(self) -> None:
        # step1: 添加任务
        self._tasks.clear()
        self.add_tasks(self._tasks)
        # step可选：混沌工程做测试
        self._context._chaos_engineering_system.on_stage_planning_system_excute(self._context)
        # step2: 并行执行requests
        if len(self._tasks) == 0:
            return
        
        tasks_gather = LangServeAgentAsyncRequestTasksGather("StagePlanningSystem", self._tasks)
        response = await tasks_gather.gather()
        if len(response) == 0:
            logger.warning(f"StagePlanningSystem: request_result is empty.")
            return

        # step3: 处理结果
        self.handle(self._tasks)
        self._tasks.clear()
#######################################################################################################################################
    def handle(self, request_tasks: Dict[str, LangServeAgentRequestTask]) -> None:

        for name, task in request_tasks.items():

            if task is None:
                logger.warning(f"StagePlanningSystem: response is None or empty, so we can't get the planning.")
                continue

            stage_entity = self._context.get_stage_entity(name)
            assert stage_entity is not None, f"StagePlanningSystem: stage_entity is None, {name}"
            if stage_entity is None:
                logger.warning(f"StagePlanningSystem: stage_entity is None, {name}")
                continue

            stage_planning = AgentPlan(name, task.response_content)
            if not self._check_plan(stage_entity, stage_planning):
                logger.warning(f"StagePlanningSystem: check_plan failed, {stage_planning}")
                ## 需要失忆!
                self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(name)
                continue
            
            ## 不能停了，只能一直继续
            for action in stage_planning._actions:
                self._add_action_component(stage_entity, action)
#######################################################################################################################################
    def _check_plan(self, entity: Entity, plan: AgentPlan) -> bool:
        if len(plan._actions) == 0:
            # 走到这里
            logger.warning(f"走到这里就是request过了，但是格式在load json的时候出了问题")
            return False

        for action in plan._actions:
            if not self._check_available(action):
                logger.warning(f"StagePlanningSystem: action is not correct, {action}")
                return False
        return True
#######################################################################################################################################
    def _check_available(self, action: AgentAction) -> bool:
        return check_component_register(action._action_name, STAGE_AVAILABLE_ACTIONS_REGISTER) is not None
#######################################################################################################################################
    def _add_action_component(self, entity: Entity, action: AgentAction) -> None:
        compclass = check_component_register(action._action_name, STAGE_AVAILABLE_ACTIONS_REGISTER)
        if compclass is None:
            return
        if not entity.has(compclass):
            entity.add(compclass, action)
#######################################################################################################################################
    # 获取场景内所有的actor的名字，用于场景计划。似乎不需要外观的信息？
    def get_actor_names_in_stage(self, entity: Entity) -> Set[str]:
        stage_comp = entity.get(StageComponent)
        actors_in_stage = self._context.actors_in_stage(stage_comp.name)
        ret: Set[str] = set()
        for actor_entity in actors_in_stage:
            actor_comp = actor_entity.get(ActorComponent)
            ret.add(actor_comp.name)
        return ret
#######################################################################################################################################
    # 获取场景内所有的道具的描述。
    def get_props_in_stage(self, entity: Entity) -> List[PropFile]:
        safe_stage_name = self._context.safe_get_entity_name(entity)
        return self._context._file_system.get_files(PropFile, safe_stage_name)
#######################################################################################################################################
    def add_tasks(self, request_tasks: Dict[str, LangServeAgentRequestTask]) -> None:
        request_tasks.clear()
        entities = self._context.get_group(Matcher(all_of=[StageComponent, AutoPlanningComponent])).entities
        for entity in entities:
            prompt = builtin_prompt.stage_plan_prompt(self.get_props_in_stage(entity), self.get_actor_names_in_stage(entity))
            stage_comp = entity.get(StageComponent)

            agent = self._context._langserve_agent_system.get_agent(stage_comp.name)
            assert agent is not None, f"StagePlanningSystem: agent is None, {stage_comp.name}"
            task = LangServeAgentRequestTask.create(agent, prompt)
            assert task is not None, f"StagePlanningSystem: create_agent_request_task failed, {stage_comp.name}"
            assert task is not None, f"StagePlanningSystem: create_agent_request_task failed, {stage_comp.name}"
            if task is not None:
                request_tasks[stage_comp.name] = task
#######################################################################################################################################