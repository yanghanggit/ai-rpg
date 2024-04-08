from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import (NPCComponent, 
                        FightActionComponent, 
                        SpeakActionComponent, 
                        LeaveForActionComponent, 
                        TagActionComponent, 
                        MindVoiceActionComponent,
                        BroadcastActionComponent, 
                        WhisperActionComponent,
                        SearchActionComponent,
                        AutoPlanningComponent,
                        RememberActionComponent)
from auxiliary.actor_action import ActorPlan, ActorAction
from auxiliary.prompt_maker import npc_plan_prompt
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from typing import Optional
from auxiliary.dialogue_rule import parse_taget_and_message

class NPCPlanningSystem(ExecuteProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
        self.dialogue_actions = [SpeakActionComponent, MindVoiceActionComponent, WhisperActionComponent]
        self.available_actions = [FightActionComponent, 
                            LeaveForActionComponent, 
                            SpeakActionComponent, 
                            TagActionComponent, 
                            RememberActionComponent,
                            MindVoiceActionComponent,
                            BroadcastActionComponent,
                            WhisperActionComponent,
                            SearchActionComponent]
####################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  NPCPlanningSystem  >>>>>>>>>>>>>>>>>")
        #记录事件
        self.context.chaos_engineering_system.on_npc_planning_system_execute(self.context)
        #正常流程
        entities = self.context.get_group(Matcher(all_of=[NPCComponent, AutoPlanningComponent])).entities
        for entity in entities:
            #开始处理NPC的行为计划
            self.handle(entity)
####################################################################################################
    def handle(self, entity: Entity) -> None:

        prompt = npc_plan_prompt(entity, self.context)
        npccomp: NPCComponent = entity.get(NPCComponent)

        response = self.requestplanning(npccomp.name, prompt)
        if response is None:
            logger.warning(f"NPCPlanningSystem: response is None or empty, so we can't get the planning.")
            return
        
        npcplanning = ActorPlan(npccomp.name, response)
        if not self.check_plan(entity, npcplanning):
            logger.warning(f"NPCPlanningSystem: check_plan failed, {npcplanning}")
            ## 需要失忆!
            self.context.agent_connect_system.remove_last_conversation_between_human_and_ai(npccomp.name)
            return
        
        ## 不能停了，只能一直继续
        for action in npcplanning.actions:
            self.add_action_component(entity, action)
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
        return action.actionname in [component.__name__ for component in self.available_actions]
####################################################################################################
    def check_dialogue(self, action: ActorAction) -> bool:
        if action.actionname not in [component.__name__ for component in self.dialogue_actions]:
            # 不是一个对话类型
            return True
    
        for value in action.values:
            pair = parse_taget_and_message(value)
            target: str = pair[0]
            message: str = pair[1]
            if target == "?":
                #格式错误
                return False
            
        #可以过
        return True
####################################################################################################
    def add_action_component(self, entity: Entity, action: ActorAction) -> bool:
        for action_component in self.available_actions:
            if action_component.__name__ != action.actionname:
                continue
            if not entity.has(action_component):
                entity.add(action_component, action)
            ## 必须跳出
            break
####################################################################################################
    def requestplanning(self, npcname: str, prompt: str) -> Optional[str]:
        #
        context = self.context
        chaos_engineering_system = context.chaos_engineering_system
        response = chaos_engineering_system.hack_npc_planning(context, npcname, prompt)
        # 可以先走混沌工程系统
        if response is None:
           response = self.context.agent_connect_system._request_(npcname, prompt)
            
        return response
####################################################################################################