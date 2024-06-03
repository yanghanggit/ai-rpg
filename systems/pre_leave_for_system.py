from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (LeaveForActionComponent, 
                        NPCComponent, 
                        StageExitCondStatusComponent,
                        StageExitCondCheckRoleStatusComponent,
                        StageExitCondCheckRolePropsComponent,
                        RoleAppearanceComponent,
                        EnviroNarrateActionComponent,
                        TagActionComponent,
                        StageEntryCondStatusComponent,
                        StageEntryCondCheckRoleStatusComponent,
                        StageEntryCondCheckRolePropsComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
#from enum import Enum
from auxiliary.director_component import notify_stage_director
# from systems.leave_for_action_system import NPCLeaveForFailedBecauseStageIsInvalidEvent, NPCLeaveForFailedBecauseAlreadyInStage
# from auxiliary.format_of_complex_stage_entry_and_exit_conditions import is_complex_stage_condition, parse_complex_stage_condition
from auxiliary.director_event import IDirectorEvent
from auxiliary.cn_builtin_prompt import \
            prop_info_prompt, stage_exit_conditions_check_promt, \
            stage_entry_conditions_check_promt,\
            exit_stage_failed_beacuse_stage_refuse_prompt, \
            enter_stage_failed_beacuse_stage_refuse_prompt, \
            NO_INFO_PROMPT
#from auxiliary.base_data import PropData
from typing import Optional, cast
from systems.check_status_action_system import CheckStatusActionHelper
from auxiliary.actor_action import ActorPlan

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
# class NPCLeaveForFailedBecauseNoExitConditionMatch(IDirectorEvent):

#     def __init__(self, npcname: str, stagename: str, tips: str, is_prison_break: bool) -> None:
#         self.npcname = npcname
#         self.stagename = stagename
#         self.tips = tips
#         self.is_prison_break = is_prison_break

#     def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
#         if npcname != self.npcname:
#             # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
#             return ""
#         return leave_for_target_stage_failed_because_no_exit_condition_match_prompt(self.npcname, self.stagename, self.tips, self.is_prison_break)
    
#     def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
#         if self.is_prison_break:
#             #如果是越狱的行动，也让场景知道，提高场景的上下文。
#             return leave_for_target_stage_failed_because_no_exit_condition_match_prompt(self.npcname, self.stagename, self.tips, self.is_prison_break)
#         return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
#todo
class NPCExitStageFailedBecauseStageRefuse(IDirectorEvent):
    def __init__(self, npcname: str, stagename: str, tips: str) -> None:
        self.npcname = npcname
        self.stagename = stagename
        self.tips = tips

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npcname:
            return ""
        return exit_stage_failed_beacuse_stage_refuse_prompt(self.npcname, self.stagename, self.tips)
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
class NPCEnterStageFailedBecauseStageRefuse(IDirectorEvent):
    def __init__(self, npcname: str, stagename: str, tips: str) -> None:
        self.npcname = npcname
        self.stagename = stagename
        self.tips = tips

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npcname:
            return ""
        return enter_stage_failed_beacuse_stage_refuse_prompt(self.npcname, self.stagename, self.tips)
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
# 错误代码
# class ErrorCheckTargetStage(Enum):
#     VALID = 0
#     ACTION_PARAMETER_ERROR = 1
#     STAGE_CANNOT_BE_FOUND = 2
#     ALREADY_IN_THIS_STAGE = 3
#     DONT_KNOW_STAGE = 4

# # 错误代码
# class ErrorCheckExitStageConditions(Enum):
#     VALID = 0
#     NO_EXIT_CONDITIONS_MATCH = 1
#     DESCRIPTION_OF_COMPLEX_CONDITION_IS_WRONG_FORMAT = 2

# # 错误代码
# class ErrorCheckEnterStageConditions(Enum):
#     VALID = 0
#     NO_ENTRY_CONDITIONS_MATCH = 1


class StageConditionsHelper:
     
    def __init__(self, tig: str) -> None:
        self.tips = tig
        self.clear()
###############################################################################################################################################
    def clear(self) -> None:
        self.stage_name = ""
        self.stage_cond_status_prompt = str(NO_INFO_PROMPT)
        self.cond_check_role_status_prompt = str(NO_INFO_PROMPT)
        self.cond_check_role_props_prompt = str(NO_INFO_PROMPT)
###############################################################################################################################################
    def prepare_exit_cond(self, stage_entity: Entity, context: ExtendedContext) -> None:
        self.clear()
        self.stage_name = context.safe_get_entity_name(stage_entity)
        # 准备好数据
        if stage_entity.has(StageExitCondStatusComponent):
            self.stage_cond_status_prompt = cast(StageExitCondStatusComponent, stage_entity.get(StageExitCondStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageExitCondCheckRoleStatusComponent):
            self.cond_check_role_status_prompt = cast(StageExitCondCheckRoleStatusComponent, stage_entity.get(StageExitCondCheckRoleStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageExitCondCheckRolePropsComponent):
            self.cond_check_role_props_prompt = cast(StageExitCondCheckRolePropsComponent, stage_entity.get(StageExitCondCheckRolePropsComponent)).condition
###############################################################################################################################################
    def prepare_entry_cond(self, stage_entity: Entity, context: ExtendedContext) -> None:
        self.clear()
        self.stage_name = context.safe_get_entity_name(stage_entity)
        # 准备好数据
        if stage_entity.has(StageEntryCondStatusComponent):
            self.stage_cond_status_prompt = cast(StageEntryCondStatusComponent, stage_entity.get(StageEntryCondStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageEntryCondCheckRoleStatusComponent):
            self.cond_check_role_status_prompt = cast(StageEntryCondCheckRoleStatusComponent, stage_entity.get(StageEntryCondCheckRoleStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageEntryCondCheckRolePropsComponent):
            self.cond_check_role_props_prompt = cast(StageEntryCondCheckRolePropsComponent, stage_entity.get(StageEntryCondCheckRolePropsComponent)).condition
###############################################################################################################################################




class HandleStageConditionsResponseHelper:
    def __init__(self, actorname: str, response: str) -> None:
        self.actorname = actorname
        self.response = response
        self.result_from_tag = False
        self.result_from_enviro_narrate = str(NO_INFO_PROMPT)

###############################################################################################################################################
    def handle(self) -> bool:
        #
        temp_plan = ActorPlan(self.actorname, self.response)
        if len(temp_plan.actions) == 0:
            logger.error("可能出现格式错误")
            return False
    
        # 再次检查是否符合结果预期
        enviro_narrate_action: Optional[ActorAction] = None
        tag_action: Optional[ActorAction] = None
        #
        for action in temp_plan.actions:
            if action.actionname == EnviroNarrateActionComponent.__name__:
                enviro_narrate_action = action
            elif action.actionname == TagActionComponent.__name__:
                tag_action = action

        if enviro_narrate_action is None or tag_action is None:
            logger.error("大模型推理错误！！！！！！！！！！！！！")
            return False
        
        # 2个结果赋值
        self.result_from_tag = self.parse_tag_action(tag_action)
        self.result_from_enviro_narrate = self.parse_enviro_narrate_action(enviro_narrate_action)
        return True
###############################################################################################################################################
    def parse_tag_action(self, tag_action: ActorAction) -> bool:
        if len(tag_action.values) == 0:
            logger.error(tag_action)
            return False
        first_tag_value_as_result = tag_action.values[0]
        if first_tag_value_as_result.lower() == "yes":
            return True
        return False
###############################################################################################################################################
    def parse_enviro_narrate_action(self, action: ActorAction) -> str:
        if len(action.values) == 0:
            #logger.error("没有行动")
            return "无可提示信息"
        single_value = action.single_value()
        return single_value
###############################################################################################################################################
class PreLeaveForSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
###############################################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(LeaveForActionComponent): GroupEvent.ADDED}
###############################################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(LeaveForActionComponent) and entity.has(NPCComponent)
###############################################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            exit_result = self.handle_exit_stage(entity)
            if not exit_result:
                entity.remove(LeaveForActionComponent)  # 停止离开！
                continue  #?
            enter_result = self.handle_enter_stage(entity)
            if not enter_result:
                entity.remove(LeaveForActionComponent)  # 停止进入
                continue  #?        
###############################################################################################################################################
    # todo!!
    def handle_exit_stage(self, entity: Entity) -> bool:
        #
        current_stage_entity = self.context.safe_get_stage_entity(entity)
        assert current_stage_entity is not None
        #
        npc_name = self.context.safe_get_entity_name(entity)
        current_stage_name = self.context.safe_get_entity_name(current_stage_entity)
        #
        stage_exit_cond_helper = StageConditionsHelper(f"离开{current_stage_name}的检查所有条件")
        stage_exit_cond_helper.prepare_exit_cond(current_stage_entity, self.context)
        # 准备好数据
        current_role_status_prompt = self.get_role_status_prompt(entity)
        current_role_props_prompt = self.get_role_props_prompt(entity)
        
        
        final_prompt = stage_exit_conditions_check_promt(npc_name, 
                                                         current_stage_name, 
                                                         stage_exit_cond_helper.stage_cond_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_role_status_prompt, 
                                                         current_role_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_role_props_prompt, 
                                                         current_role_props_prompt)

        logger.debug(final_prompt)

        ## 让大模型去推断是否可以离开，分别检查stage自身，角色状态（例如长相），角色道具（拥有哪些道具与文件）
        agent_connect_system = self.context.agent_connect_system
        respones = agent_connect_system.request(current_stage_name, final_prompt)
        if respones is None:
            logger.error("没有回应！！！！！！！！！！！！！")
            return False
        
        logger.debug(f"大模型推理后的结果: {respones}")
        handle_response_helper = HandleStageConditionsResponseHelper(current_stage_name, respones)
        if not handle_response_helper.handle():
            return False
        
        #
        if not handle_response_helper.result_from_tag:
            # 通知事件
            notify_stage_director(self.context, 
                                  current_stage_entity, 
                                  NPCExitStageFailedBecauseStageRefuse(npc_name, current_stage_name, handle_response_helper.result_from_enviro_narrate))
            return False

        logger.info(f"允许通过！说明如下: {handle_response_helper.result_from_enviro_narrate}")
        ## 可以删除，允许通过！这个上下文就拿掉，不需要了。
        agent_connect_system = self.context.agent_connect_system
        agent_connect_system.remove_last_conversation_between_human_and_ai(current_stage_name)
        return True
###############################################################################################################################################
    def handle_enter_stage(self, entity: Entity) -> bool:
        target_stage_entity = self.get_target_stage_entity(entity)
        if target_stage_entity is None:
            return False
        
        ##
        npc_name = self.context.safe_get_entity_name(entity)
        target_stage_name = self.context.safe_get_entity_name(target_stage_entity)
        #
        stage_exit_cond_helper = StageConditionsHelper(f"进入{target_stage_name}的检查所有条件")
        stage_exit_cond_helper.prepare_entry_cond(target_stage_entity, self.context)
        # 准备好数据
        current_role_status_prompt = self.get_role_status_prompt(entity)
        current_role_props_prompt = self.get_role_props_prompt(entity)
        # 最终提示词
        final_prompt = stage_entry_conditions_check_promt(npc_name, 
                                                         target_stage_name, 
                                                         stage_exit_cond_helper.stage_cond_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_role_status_prompt, 
                                                         current_role_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_role_props_prompt, 
                                                         current_role_props_prompt)

        logger.debug(final_prompt)

        ## 让大模型去推断是否可以离开，分别检查stage自身，角色状态（例如长相），角色道具（拥有哪些道具与文件）
        agent_connect_system = self.context.agent_connect_system
        respones = agent_connect_system.request(target_stage_name, final_prompt)
        if respones is None:
            logger.error("没有回应！！！！！！！！！！！！！")
            return False
        
        logger.debug(f"大模型推理后的结果: {respones}")
        handle_response_helper = HandleStageConditionsResponseHelper(target_stage_name, respones)
        if not handle_response_helper.handle():
            return False
        
        if not handle_response_helper.result_from_tag:
            # 通知事件
            notify_stage_director(self.context, 
                                  target_stage_entity, 
                                  NPCEnterStageFailedBecauseStageRefuse(npc_name, target_stage_name, handle_response_helper.result_from_enviro_narrate))
            return False

        logger.info(f"允许通过！说明如下: {handle_response_helper.result_from_enviro_narrate}")
        ## 可以删除，允许通过！这个上下文就拿掉，不需要了。
        agent_connect_system = self.context.agent_connect_system
        agent_connect_system.remove_last_conversation_between_human_and_ai(target_stage_name)
        return True
###############################################################################################################################################
    def get_target_stage_entity(self, entity: Entity) -> Optional[Entity]:
        leave_action_comp: LeaveForActionComponent = entity.get(LeaveForActionComponent)
        action: ActorAction = leave_action_comp.action
        if len(action.values) == 0:
            logger.error(leave_action_comp)
            return None
        #
        target_stage_name = action.values[0]
        stageentity = self.context.getstage(target_stage_name)
        return stageentity
###############################################################################################################################################
    def get_role_status_prompt(self, entity: Entity) -> str:
        safe_name = self.context.safe_get_entity_name(entity)
        role_appearance_comp: RoleAppearanceComponent = entity.get(RoleAppearanceComponent)
        appearance_info: str = role_appearance_comp.appearance
        return f"""### {safe_name}\n- 外貌信息:{appearance_info}\n"""
###############################################################################################################################################
    def get_role_props_prompt(self, entity: Entity) -> str:
        helper = CheckStatusActionHelper(self.context)
        helper.check_status(entity)
        props = helper.props + helper.role_components
        prompt_of_props = ""
        if len(props) > 0:
            for prop in props:
                prompt_of_props += prop_info_prompt(prop)
        else:
            prompt_of_props = "- 无任何道具或者特殊技能"
        return prompt_of_props
###############################################################################################################################################
    
    
    
    
    
    
    
    
    
    
    
# #下面是旧的代码！！！！！！！！！
# ###############################################################################################################################################
# ###############################################################################################################################################
# ###############################################################################################################################################
# ###############################################################################################################################################
# ###############################################################################################################################################
# ###############################################################################################################################################
# ###############################################################################################################################################
# ###############################################################################################################################################
# ###############################################################################################################################################
#     def old_handle_react(self, entities: list[Entity]) -> None:
#         for entity in entities:
#             if not self.check_current_stage_valid(entity):
#                 #logger.error("场景有问题")
#                 continue

#             error_check_target_stage = self.check_target_stage_valid(entity)
#             if error_check_target_stage != ErrorCheckTargetStage.VALID:
#                 # 要去往的场景有问题
#                 self.handle_target_stage_invalid(entity, error_check_target_stage)
#                 continue

#             exit_error = self.check_exit_stage_conditions(entity)
#             if exit_error != ErrorCheckExitStageConditions.VALID:
#                 # 离开限制
#                 self.handle_exit_stage_conditions_invalid(entity, exit_error)
#                 continue
            
#             enter_error = self.check_enter_stage_conditions(entity)
#             if enter_error != ErrorCheckEnterStageConditions.VALID:
#                 # 进入限制
#                 self.handle_enter_stage_conditions_invalid(entity, enter_error)
#                 continue
# ###############################################################################################################################################
#     def check_current_stage_valid(self, entity: Entity) -> bool:
#         npccomp: NPCComponent = entity.get(NPCComponent)
#         current_stage: str = npccomp.current_stage
#         stageentity = self.context.getstage(current_stage)
#         if stageentity is None:
#             logger.error(f"{current_stage},场景有问题")
#             return False
#         return True
# ###############################################################################################################################################
#     def check_target_stage_valid(self, entity: Entity) -> ErrorCheckTargetStage:
#         #
#         file_system = self.context.file_system
#         npccomp: NPCComponent = entity.get(NPCComponent)
#         #
#         leavecomp: LeaveForActionComponent = entity.get(LeaveForActionComponent)
#         action: ActorAction = leavecomp.action
#         if len(action.values) == 0:
#            logger.error("参数错误")
#            return ErrorCheckTargetStage.ACTION_PARAMETER_ERROR
#         #
#         targetstagename = action.values[0]
#         targetstage = self.context.getstage(targetstagename)
#         if targetstage is None:
#             logger.error(f"找不到这个场景: {targetstagename}")
#             return ErrorCheckTargetStage.STAGE_CANNOT_BE_FOUND
#         #
#         if targetstagename == npccomp.current_stage:
#             logger.error(f"{npccomp.name} 已经在这个场景: {targetstagename}")
#             return ErrorCheckTargetStage.ALREADY_IN_THIS_STAGE
        
#         #
#         knownstagefile = file_system.get_stage_archive_file(npccomp.name, targetstagename)
#         if knownstagefile is None:
#             # 我不认识该怎么办？
#             if entity.has(PrisonBreakActionComponent):
#                 logger.info(f"{npccomp.name} 逃狱了，但不知道这个场景: {targetstagename}。没关系只要目标场景是合理的，系统可以放过去")
#             else:
#                 logger.error(f"{npccomp.name} 不知道这个场景: {targetstagename}，而且不是逃狱。就是不能去")
#                 return ErrorCheckTargetStage.DONT_KNOW_STAGE
#         #
#         return ErrorCheckTargetStage.VALID
# ###############################################################################################################################################
#     def handle_target_stage_invalid(self, entity: Entity, error: ErrorCheckTargetStage) -> None:

#         leavecomp: LeaveForActionComponent = entity.get(LeaveForActionComponent)
#         action: ActorAction = leavecomp.action
#         safe_npc_name = self.context.safe_get_entity_name(entity)
        
#         # step1 加入通知事件，更新记忆，如果出了问题可以在这个环节做矫正
#         if error == ErrorCheckTargetStage.STAGE_CANNOT_BE_FOUND:
#             notify_stage_director(self.context, entity, NPCLeaveForFailedBecauseStageIsInvalidEvent(safe_npc_name, action.values[0]))
#         elif error == ErrorCheckTargetStage.ALREADY_IN_THIS_STAGE:
#             notify_stage_director(self.context, entity, NPCLeaveForFailedBecauseAlreadyInStage(safe_npc_name, action.values[0]))

#         # step2 最后删除
#         entity.remove(LeaveForActionComponent) # 停止离开！
# ###############################################################################################################################################
#     def check_npc_file_valid(self, ownername: str, filename: str) -> bool:
#         return self.context.file_system.has_prop_file(ownername, filename) or self.context.file_system.has_prop_file(ownername, filename)
# ###############################################################################################################################################
#     def check_exit_stage_conditions(self, entity: Entity) -> ErrorCheckExitStageConditions:
#         #
#         file_system = self.context.file_system
#         npccomp: NPCComponent = entity.get(NPCComponent)
#         current_stage: str = npccomp.current_stage
#         stageentity = self.context.getstage(current_stage)
#         assert stageentity is not None

#         # 没有离开条件，无需讨论
#         if not stageentity.has(StageExitConditionComponent):
#             return ErrorCheckExitStageConditions.VALID
        
#         #有检查条件
#         exit_condition_comp: StageExitConditionComponent = stageentity.get(StageExitConditionComponent)
#         conditions: set[str] = exit_condition_comp.conditions
#         if len(conditions) == 0:
#             #空的，就过
#             return ErrorCheckExitStageConditions.VALID
        
#         ### 检查条件
#         for cond in conditions:
#             # 如果是复杂型条件的文本
#             if is_complex_stage_condition(cond):
#                 res = parse_complex_stage_condition(cond)
#                 if len(res) != 2:
#                     logger.error(f"复杂条件的描述格式错误: {cond}")
#                     return ErrorCheckExitStageConditions.DESCRIPTION_OF_COMPLEX_CONDITION_IS_WRONG_FORMAT
                
#                 propname = res[0]
#                 tips = res[1]
#                 if not self.check_npc_file_valid(npccomp.name, propname):
#                     # 没有这个道具
#                     logger.info(f"{npccomp.name} 没有这个道具: {propname}。提示: {tips}")
#                     return ErrorCheckExitStageConditions.NO_EXIT_CONDITIONS_MATCH

#             elif not self.check_npc_file_valid(npccomp.name, propname):
#                 # 没有这个道具
#                 return ErrorCheckExitStageConditions.NO_EXIT_CONDITIONS_MATCH
#         ##
#         return ErrorCheckExitStageConditions.VALID
# ###############################################################################################################################################
#     def handle_exit_stage_conditions_invalid(self, entity: Entity, error: ErrorCheckExitStageConditions) -> None:
#         if error == ErrorCheckExitStageConditions.NO_EXIT_CONDITIONS_MATCH:
#             self.notify_director_no_exit_conditions_match(entity)
#         elif error == ErrorCheckExitStageConditions.DESCRIPTION_OF_COMPLEX_CONDITION_IS_WRONG_FORMAT:
#             logger.error("复杂条件的描述格式错误，估计就是表格填错了")

#         # 最后必须停止离开
#         entity.remove(LeaveForActionComponent) # 停止离开！
# ###############################################################################################################################################
#     def notify_director_no_exit_conditions_match(self, entity: Entity) -> None:
#         file_system = self.context.file_system
#         stageentity = self.context.safe_get_stage_entity(entity)
#         if stageentity is None:
#             return
#         #
#         exit_condition_comp: StageExitConditionComponent = stageentity.get(StageExitConditionComponent)
#         #
#         safe_npc_name = self.context.safe_get_entity_name(entity)
#         leavecomp: LeaveForActionComponent = entity.get(LeaveForActionComponent)
#         action: ActorAction = leavecomp.action
#         stagename = action.values[0]
        
#         conditions: set[str] = exit_condition_comp.conditions
#         assert len(conditions) > 0

#         # 如果越狱，在提示词里要隐藏掉去往的地名
#         is_prison_break = entity.has(PrisonBreakActionComponent)

#         for cond in conditions:
#             # 如果是复杂型条件的文本
#             if is_complex_stage_condition(cond):
#                 res = parse_complex_stage_condition(cond)
#                 assert len(res) == 2
#                 propname = res[0]
#                 tips = res[1]
#                 if not file_system.has_prop_file(safe_npc_name, propname):
#                     # 没有这个道具
#                     logger.info(f"{safe_npc_name} 没有这个道具: {propname}。提示: {tips}")
#                     notify_stage_director(self.context, stageentity, NPCLeaveForFailedBecauseNoExitConditionMatch(safe_npc_name, stagename, tips, is_prison_break))
#                     break

#             elif not file_system.has_prop_file(safe_npc_name, cond):
#                 notify_stage_director(self.context, stageentity, NPCLeaveForFailedBecauseNoExitConditionMatch(safe_npc_name, stagename, "", is_prison_break))
#                 break
# ###############################################################################################################################################
#     def check_enter_stage_conditions(self, entity: Entity) -> ErrorCheckEnterStageConditions:
#         #
#         file_system = self.context.file_system
#         npccomp: NPCComponent = entity.get(NPCComponent)

#         leavecomp: LeaveForActionComponent = entity.get(LeaveForActionComponent)
#         action: ActorAction = leavecomp.action
        
#         targetstagename = action.values[0]
#         targetstage = self.context.getstage(targetstagename)
#         assert targetstage is not None
#         if not targetstage.has(StageEntryConditionComponent):
#             return ErrorCheckEnterStageConditions.VALID
        
#         #有检查条件
#         entry_condition_comp: StageEntryConditionComponent = targetstage.get(StageEntryConditionComponent)
#         conditions = entry_condition_comp.conditions
#         if len(conditions) == 0:
#             return ErrorCheckEnterStageConditions.VALID
        
#         ### 检查条件
#         for cond in conditions:
#             if file_system.has_prop_file(npccomp.name, cond):
#                 return ErrorCheckEnterStageConditions.VALID
        
#         # 没有这个道具
#         return ErrorCheckEnterStageConditions.NO_ENTRY_CONDITIONS_MATCH
# ###############################################################################################################################################
#     def handle_enter_stage_conditions_invalid(self, entity: Entity, error: ErrorCheckEnterStageConditions) -> None:
#         entity.remove(LeaveForActionComponent) # 停止离开！
#         pass
###############################################################################################################################################    
