from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import (StageComponent, 
                        AutoPlanningComponent,
                        stage_available_actions_register,
                        stage_dialogue_actions_register)
from auxiliary.actor_action import ActorPlan, ActorAction
from auxiliary.prompt_maker import stage_plan_prompt
from auxiliary.extended_context import ExtendedContext
from loguru import logger 
from typing import Optional

####################################################################################################    
class StagePlanningSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
####################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  StagePlanningSystem  >>>>>>>>>>>>>>>>>")
        #记录事件
        self.context.chaos_engineering_system.on_stage_planning_system_excute(self.context)
        #正常流程
        entities = self.context.get_group(Matcher(all_of=[StageComponent, AutoPlanningComponent])).entities
        for entity in entities:
            ## 开始处理场景的行为与计划
            self.handle(entity)
####################################################################################################
    def handle(self, entity: Entity) -> None:
        
        prompt = stage_plan_prompt(entity, self.context)
        stagecomp: StageComponent = entity.get(StageComponent)

        response = self.requestplanning(stagecomp.name, prompt)
        if response is None:
            logger.warning(f"StagePlanningSystem: response is None or empty, so we can't get the planning.")
            return
        
        stageplanning = ActorPlan(stagecomp.name, response)
        if not self.check_plan(entity, stageplanning):
            logger.warning(f"StagePlanningSystem: check_plan failed, {stageplanning}")
            ## 需要失忆!
            self.context.agent_connect_system.remove_last_conversation_between_human_and_ai(stagecomp.name)
            return
        
        ## 不能停了，只能一直继续
        for action in stageplanning.actions:
            self.add_action_component(entity, action)
####################################################################################################
    def requestplanning(self, stagename: str, prompt: str) -> Optional[str]:
        #
        context = self.context
        chaos_engineering_system = context.chaos_engineering_system
        # 可以先走混沌工程系统
        response = chaos_engineering_system.hack_stage_planning(context, stagename, prompt)
        if response is None:
            response = self.context.agent_connect_system.request(stagename, prompt)

        return response
####################################################################################################
    def check_plan(self, entity: Entity, plan: ActorPlan) -> bool:
        if len(plan.actions) == 0:
            # 走到这里
            logger.warning(f"走到这里就是request过了，但是格式在load json的时候出了问题")
            return False

        for action in plan.actions:
            if not self.check_available(action):
                logger.warning(f"StagePlanningSystem: action is not correct, {action}")
                return False
            if not self.check_dialogue(action):
                logger.warning(f"StagePlanningSystem: target or message is not correct, {action}")
                return False
        return True
####################################################################################################
    def check_available(self, action: ActorAction) -> bool:
        return self.context.check_component_register(action.actionname, stage_available_actions_register) is not None
####################################################################################################
    def check_dialogue(self, action: ActorAction) -> bool:
        return self.context.check_dialogue_action(action.actionname, action.values, stage_dialogue_actions_register)
####################################################################################################
    def add_action_component(self, entity: Entity, action: ActorAction) -> None:
        compclass = self.context.check_component_register(action.actionname, stage_available_actions_register)
        if compclass is None:
            return
        if not entity.has(compclass):
            entity.add(compclass, action)
####################################################################################################