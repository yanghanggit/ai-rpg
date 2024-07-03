from overrides import override
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from ecs_systems.components import (ActorComponent, AutoPlanningComponent, EnviroNarrateActionComponent, ACTOR_CONVERSATION_ACTIONS_REGISTER, 
                                  ACTOR_AVAILABLE_ACTIONS_REGISTER)
from my_agent.agent_plan import AgentPlan
from my_agent.agent_action import AgentAction
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from typing import Optional, Dict
from gameplay_checks.planning_check import check_component_register
from builtin_prompt.cn_builtin_prompt import actpr_plan_prompt


class ActorPlanningSystem(ExecuteProcessor):

    """
    角色的计划系统，必须在StagePlanningSystem之后执行
    """

    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
#######################################################################################################################################
    @override
    def execute(self) -> None:
        pass
#######################################################################################################################################
    @override
    async def async_pre_execute(self) -> None:
         # step1: 添加任务
        self.add_tasks()
        # step可选：混沌工程做测试
        self.context._chaos_engineering_system.on_actor_planning_system_execute(self.context)
        # step2: 并行执行requests
        request_result = await self.context._langserve_agent_system.request_tasks("ActorPlanningSystem")
        if len(request_result) == 0:
            logger.warning(f"ActorPlanningSystem: request_result is empty.")
            return
        self.handle(request_result[0])
#######################################################################################################################################
    def handle(self, response_map: Dict[str, Optional[str]]) -> None:
        for name, response in response_map.items():

            if response is None:
                logger.warning(f"ActorPlanningSystem: response is None or empty, so we can't get the planning.")
                continue
            
            entity = self.context.get_actor_entity(name)
            assert entity is not None, f"ActorPlanningSystem: entity is None, {name}"
            if entity is None:
                logger.warning(f"ActorPlanningSystem: entity is None, {name}")
                continue

            actor_comp = entity.get(ActorComponent)
            actor_planning = AgentPlan(actor_comp.name, response)
            if not self._check_plan(entity, actor_planning):
                logger.warning(f"ActorPlanningSystem: check_plan failed, {actor_planning}")
                ## 需要失忆!
                self.context._langserve_agent_system.remove_last_conversation_between_human_and_ai(actor_comp.name)
                continue
            
            ## 不能停了，只能一直继续
            for action in actor_planning.actions:
                self._add_action_component(entity, action)
#######################################################################################################################################
    def _check_plan(self, entity: Entity, plan: AgentPlan) -> bool:
        if len(plan.actions) == 0:
            # 走到这里
            logger.warning(f"走到这里就是request过了，但是格式在load json的时候出了问题")
            return False

        for action in plan.actions:
            if not self._check_available(action):
                logger.warning(f"ActorPlanningSystem: action is not correct, {action}")
                return False
            # if not self._check_conversation(action):
            #     logger.warning(f"ActorPlanningSystem: target or message is not correct, {action}")
            #     return False
        return True
#######################################################################################################################################
    def _check_available(self, action: AgentAction) -> bool:
        return check_component_register(action._action_name, ACTOR_AVAILABLE_ACTIONS_REGISTER) is not None
#######################################################################################################################################
    # def _check_conversation(self, action: ActorAction) -> bool:
    #     return check_conversation_action(action, ACTOR_CONVERSATION_ACTIONS_REGISTER)
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

        stage_entity = self.context.safe_get_stage_entity(entity)
        if stage_entity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
            return "", ""
        
        stagename = self.context.safe_get_entity_name(stage_entity)
        stage_enviro_narrate = ""
        if stage_entity.has(EnviroNarrateActionComponent):
            envirocomp = stage_entity.get(EnviroNarrateActionComponent)
            action: AgentAction = envirocomp.action
            stage_enviro_narrate = action.join_values()
                
        return stagename, stage_enviro_narrate
#######################################################################################################################################
    def add_tasks(self) -> None:
        entities = self.context.get_group(Matcher(all_of=[ActorComponent, AutoPlanningComponent])).entities
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
            self.context._langserve_agent_system.add_request_task(actor_comp.name, prompt)
#######################################################################################################################################