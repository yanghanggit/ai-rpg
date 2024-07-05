from overrides import override
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from ecs_systems.components import (ActorComponent, AutoPlanningComponent, EnviroNarrateActionComponent, 
                                  ACTOR_AVAILABLE_ACTIONS_REGISTER)
from my_agent.agent_plan import AgentPlan
from my_agent.agent_action import AgentAction
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from typing import Dict
from gameplay_checks.planning_check import check_component_register
from builtin_prompt.cn_builtin_prompt import actpr_plan_prompt
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask, LangServeAgentAsyncRequestTasksGather


class ActorPlanningSystem(ExecuteProcessor):

    """
    角色的计划系统，必须在StagePlanningSystem之后执行
    """

    def __init__(self, context: ExtendedContext) -> None:
        self._context = context
        self._request_tasks: Dict[str, LangServeAgentRequestTask] = {}
#######################################################################################################################################
    @override
    def execute(self) -> None:
        pass
#######################################################################################################################################
    @override
    async def async_pre_execute(self) -> None:
        # step1: 添加任务
        self._request_tasks.clear()
        self.add_tasks(self._request_tasks)
        # step可选：混沌工程做测试
        self._context._chaos_engineering_system.on_actor_planning_system_execute(self._context)
        # step2: 并行执行requests
        if len(self._request_tasks) == 0:
            return
        
        tasks_gather = LangServeAgentAsyncRequestTasksGather("ActorPlanningSystem Gather", self._request_tasks)
        request_result = await tasks_gather.gather()
        if len(request_result) == 0:
            logger.warning(f"ActorPlanningSystem: request_result is empty.")
            return

        self.handle(self._request_tasks)
        self._request_tasks.clear()
#######################################################################################################################################
    def handle(self, request_tasks: Dict[str, LangServeAgentRequestTask]) -> None:
        for name, task in request_tasks.items():

            if task is None:
                logger.warning(f"ActorPlanningSystem: response is None or empty, so we can't get the planning.")
                continue
            
            entity = self._context.get_actor_entity(name)
            assert entity is not None, f"ActorPlanningSystem: entity is None, {name}"
            if entity is None:
                logger.warning(f"ActorPlanningSystem: entity is None, {name}")
                continue

            actor_comp = entity.get(ActorComponent)
            actor_planning = AgentPlan(actor_comp.name, task.response_content)
            if not self._check_plan(entity, actor_planning):
                logger.warning(f"ActorPlanningSystem: check_plan failed, {actor_planning}")
                ## 需要失忆!
                self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(actor_comp.name)
                continue
            
            ## 不能停了，只能一直继续
            for action in actor_planning._actions:
                self._add_action_component(entity, action)
#######################################################################################################################################
    def _check_plan(self, entity: Entity, plan: AgentPlan) -> bool:
        if len(plan._actions) == 0:
            # 走到这里
            logger.warning(f"走到这里就是request过了，但是格式在load json的时候出了问题")
            return False

        for action in plan._actions:
            if not self._check_available(action):
                logger.warning(f"ActorPlanningSystem: action is not correct, {action}")
                return False
        return True
#######################################################################################################################################
    def _check_available(self, action: AgentAction) -> bool:
        return check_component_register(action._action_name, ACTOR_AVAILABLE_ACTIONS_REGISTER) is not None
#######################################################################################################################################
    def _add_action_component(self, entity: Entity, action: AgentAction) -> None:
        compclass = check_component_register(action._action_name, ACTOR_AVAILABLE_ACTIONS_REGISTER)
        if compclass is None:
            return
        if not entity.has(compclass):
            entity.add(compclass, action)
#######################################################################################################################################
    # 获取场景的环境描述
    def get_stage_enviro_narrate(self, entity: Entity) -> tuple[str, str]:

        stage_entity = self._context.safe_get_stage_entity(entity)
        if stage_entity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
            return "", ""
        
        stage_name = self._context.safe_get_entity_name(stage_entity)
        stage_enviro_narrate = ""
        if stage_entity.has(EnviroNarrateActionComponent):
            envirocomp = stage_entity.get(EnviroNarrateActionComponent)
            action: AgentAction = envirocomp.action
            stage_enviro_narrate = action.join_values()
                
        return stage_name, stage_enviro_narrate
#######################################################################################################################################
    def add_tasks(self, request_tasks: Dict[str, LangServeAgentRequestTask]) -> None:
        request_tasks.clear()

        entities = self._context.get_group(Matcher(all_of=[ActorComponent, AutoPlanningComponent])).entities
        for entity in entities:
            actor_comp = entity.get(ActorComponent)
            tp = self.get_stage_enviro_narrate(entity)
            stage_name = tp[0]
            stage_enviro_narrate = tp[1]
            if stage_name == "" or stage_enviro_narrate == "":
                logger.error("stagename or stage_enviro_narrate is None, 有可能是是没有agent connect") # 放弃这个actor的计划
                continue
            
            # 必须要有一个stage的环境描述，否则无法做计划。
            prompt = actpr_plan_prompt(stage_name, stage_enviro_narrate)
            task = self._context._langserve_agent_system.create_agent_request_task(actor_comp.name, prompt)
            assert task is not None, f"ActorPlanningSystem: task is None, {actor_comp.name}"
            if task is not None:
                request_tasks[actor_comp.name] = task
#######################################################################################################################################