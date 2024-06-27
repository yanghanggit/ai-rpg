from overrides import override
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import (StageComponent, AutoPlanningComponent, ActorComponent, STAGE_AVAILABLE_ACTIONS_REGISTER, STAGE_CONVERSATION_ACTIONS_REGISTER)
from auxiliary.actor_plan_and_action import ActorPlan, ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger 
from typing import Optional, Dict, Set, List
from systems.planning_response_check import check_component_register, check_conversation_action
from prototype_data.data_def import PropData
from builtin_prompt.cn_builtin_prompt import stage_plan_prompt

#######################################################################################################################################
class StagePlanningSystem(ExecuteProcessor):

    """
    场景计划系统
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
        self.context.chaos_engineering_system.on_stage_planning_system_excute(self.context)
        # step2: 并行执行requests
        tasks_result = await self.context.agent_connect_system.run_async_requet_tasks("StagePlanningSystem")
        if len(tasks_result) == 0:
            logger.warning(f"StagePlanningSystem: tasks_result is empty.")
            return
        # step3: 处理结果
        self.handle(tasks_result[0])
#######################################################################################################################################
    def handle(self, response_map: Dict[str, Optional[str]]) -> None:

        for name, response in response_map.items():

            if response is None:
                logger.warning(f"StagePlanningSystem: response is None or empty, so we can't get the planning.")
                continue

            stage_entity = self.context.get_stage_entity(name)
            assert stage_entity is not None, f"StagePlanningSystem: stage_entity is None, {name}"
            if stage_entity is None:
                logger.warning(f"StagePlanningSystem: stage_entity is None, {name}")
                continue

            stage_planning = ActorPlan(name, response)
            if not self._check_plan(stage_entity, stage_planning):
                logger.warning(f"StagePlanningSystem: check_plan failed, {stage_planning}")
                ## 需要失忆!
                self.context.agent_connect_system.remove_last_conversation_between_human_and_ai(name)
                continue
            
            ## 不能停了，只能一直继续
            for action in stage_planning.actions:
                self._add_action_component(stage_entity, action)
#######################################################################################################################################
    def _check_plan(self, entity: Entity, plan: ActorPlan) -> bool:
        if len(plan.actions) == 0:
            # 走到这里
            logger.warning(f"走到这里就是request过了，但是格式在load json的时候出了问题")
            return False

        for action in plan.actions:
            if not self._check_available(action):
                logger.warning(f"StagePlanningSystem: action is not correct, {action}")
                return False
            if not self._check_conversation(action):
                logger.warning(f"StagePlanningSystem: target or message is not correct, {action}")
                return False
        return True
#######################################################################################################################################
    def _check_available(self, action: ActorAction) -> bool:
        return check_component_register(action.actionname, STAGE_AVAILABLE_ACTIONS_REGISTER) is not None
#######################################################################################################################################
    def _check_conversation(self, action: ActorAction) -> bool:
        return check_conversation_action(action.actionname, action.values, STAGE_CONVERSATION_ACTIONS_REGISTER)
#######################################################################################################################################
    def _add_action_component(self, entity: Entity, action: ActorAction) -> None:
        compclass = check_component_register(action.actionname, STAGE_AVAILABLE_ACTIONS_REGISTER)
        if compclass is None:
            return
        if not entity.has(compclass):
            entity.add(compclass, action)
#######################################################################################################################################
    # 获取场景内所有的actor的名字，用于场景计划。似乎不需要外观的信息？
    def get_actor_names_in_stage(self, entity: Entity) -> Set[str]:
        stage_comp: StageComponent = entity.get(StageComponent)
        _actors_in_stage = self.context.actors_in_stage(stage_comp.name)
        _names: Set[str] = set()
        for _en in _actors_in_stage:
            actor_comp: ActorComponent = _en.get(ActorComponent)
            _names.add(actor_comp.name)
        return _names
#######################################################################################################################################
    # 获取场景内所有的道具的描述。
    def get_props_in_stage(self, entity: Entity) -> List[PropData]:
        res: List[PropData] = []
        filesystem = self.context.file_system
        safe_stage_name = self.context.safe_get_entity_name(entity)
        files = filesystem.get_prop_files(safe_stage_name)
        for file in files:
            res.append(file._prop)
        return res
#######################################################################################################################################
    def add_tasks(self) -> None:
        entities = self.context.get_group(Matcher(all_of=[StageComponent, AutoPlanningComponent])).entities
        for entity in entities:
            prompt = stage_plan_prompt(self.get_props_in_stage(entity), self.get_actor_names_in_stage(entity), self.context)
            stage_comp: StageComponent = entity.get(StageComponent)
            self.context.agent_connect_system.add_async_request_task(stage_comp.name, prompt)
#######################################################################################################################################