from overrides import override
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import (ActorComponent, 
                        AutoPlanningComponent,
                        ACTOR_DIALOGUE_ACTIONS_REGISTER, 
                        ACTOR_AVAILABLE_ACTIONS_REGISTER)
from auxiliary.actor_plan_and_action import ActorPlan, ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from typing import Optional
from systems.planning_response_check import check_component_register, check_conversation_action


class NPCPlanningSystem(ExecuteProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
####################################################################################################
    @override
    def execute(self) -> None:
        pass
####################################################################################################
    @override
    async def async_pre_execute(self) -> None:
        #记录事件
        self.context.chaos_engineering_system.on_npc_planning_system_execute(self.context)
        # 并行执行requests
        request_result = await self.context.agent_connect_system.run_async_requet_tasks("NPCPlanningSystem")
        all_response: dict[str, Optional[str]] = request_result[0]
        #正常流程
        entities = self.context.get_group(Matcher(all_of=[ActorComponent, AutoPlanningComponent])).entities
        for entity in entities:
            #开始处理NPC的行为计划
            self.handle(entity, all_response)
####################################################################################################
    def handle(self, entity: Entity, all_reponse: dict[str, Optional[str]]) -> None:

        # prompt = npc_plan_prompt(entity, self.context)
        npc_comp: ActorComponent = entity.get(ActorComponent)

        # response = self.requestplanning(npccomp.name, prompt)
        response = all_reponse.get(npc_comp.name, None)
        if response is None:
            logger.warning(f"NPCPlanningSystem: response is None or empty, so we can't get the planning.")
            return
        
        npc_planning = ActorPlan(npc_comp.name, response)
        if not self.check_plan(entity, npc_planning):
            logger.warning(f"NPCPlanningSystem: check_plan failed, {npc_planning}")
            ## 需要失忆!
            self.context.agent_connect_system.remove_last_conversation_between_human_and_ai(npc_comp.name)
            return
        
        ## 不能停了，只能一直继续
        for action in npc_planning.actions:
            self.add_action_component(entity, action)
####################################################################################################
    def requestplanning(self, npcname: str, prompt: str) -> Optional[str]:
        #
        context = self.context
        chaos_engineering_system = context.chaos_engineering_system
        response = chaos_engineering_system.hack_npc_planning(context, npcname, prompt)
        # 可以先走混沌工程系统
        if response is None:
           response = self.context.agent_connect_system.agent_request(npcname, prompt)
            
        return response
####################################################################################################
    def check_plan(self, entity: Entity, plan: ActorPlan) -> bool:
        if len(plan.actions) == 0:
            # 走到这里
            logger.warning(f"走到这里就是request过了，但是格式在load json的时候出了问题")
            return False

        for action in plan.actions:
            if not self.check_available(action):
                logger.warning(f"NPCPlanningSystem: action is not correct, {action}")
                return False
            if not self.check_dialogue(action):
                logger.warning(f"NPCPlanningSystem: target or message is not correct, {action}")
                return False
        return True
####################################################################################################
    def check_available(self, action: ActorAction) -> bool:
        return check_component_register(action.actionname, ACTOR_AVAILABLE_ACTIONS_REGISTER) is not None
####################################################################################################
    def check_dialogue(self, action: ActorAction) -> bool:
        return check_conversation_action(action.actionname, action.values, ACTOR_DIALOGUE_ACTIONS_REGISTER)
####################################################################################################
    def add_action_component(self, entity: Entity, action: ActorAction) -> None:
        compclass = check_component_register(action.actionname, ACTOR_AVAILABLE_ACTIONS_REGISTER)
        if compclass is None:
            return
        if not entity.has(compclass):
            entity.add(compclass, action)
####################################################################################################