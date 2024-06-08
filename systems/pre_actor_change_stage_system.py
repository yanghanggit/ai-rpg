from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (GoToActionComponent, 
                        ActorComponent, 
                        StageExitCondStatusComponent,
                        StageExitCondCheckRoleStatusComponent,
                        StageExitCondCheckRolePropsComponent,
                        AppearanceComponent,
                        EnviroNarrateActionComponent,
                        TagActionComponent,
                        StageEntryCondStatusComponent,
                        StageEntryCondCheckRoleStatusComponent,
                        StageEntryCondCheckRolePropsComponent,
                        DeadActionComponent)
from auxiliary.actor_plan_and_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import IDirectorEvent
from auxiliary.cn_builtin_prompt import \
            prop_info_prompt, stage_exit_conditions_check_promt, \
            stage_entry_conditions_check_promt,\
            exit_stage_failed_beacuse_stage_refuse_prompt, \
            enter_stage_failed_beacuse_stage_refuse_prompt, \
            NO_INFO_PROMPT,\
            NO_ROLE_PROPS_INFO_PROMPT, \
            role_status_info_when_pre_leave_prompt
from typing import Optional, cast, override
from systems.check_status_action_system import CheckStatusActionHelper
from auxiliary.actor_plan_and_action import ActorPlan


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorExitStageFailedBecauseStageRefuse(IDirectorEvent):
    def __init__(self, actor_name: str, stagename: str, tips: str) -> None:
        self.actor_name = actor_name
        self.stagename = stagename
        self.tips = tips

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self.actor_name:
            return ""
        return exit_stage_failed_beacuse_stage_refuse_prompt(self.actor_name, self.stagename, self.tips)
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorEnterStageFailedBecauseStageRefuse(IDirectorEvent):
    def __init__(self, actor_name: str, stagename: str, tips: str) -> None:
        self.actor_name = actor_name
        self.stagename = stagename
        self.tips = tips

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self.actor_name:
            return ""
        return enter_stage_failed_beacuse_stage_refuse_prompt(self.actor_name, self.stagename, self.tips)
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
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
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################

class HandleStageConditionsResponseHelper:
    def __init__(self, plan: ActorPlan) -> None:
        self._plan = plan
        self._result = False
        self._tips = str(NO_INFO_PROMPT)
###############################################################################################################################################
    @property
    def result(self) -> bool:
        return self._result
###############################################################################################################################################
    @property
    def tips(self) -> str:
        return self._tips
###############################################################################################################################################
    def handle(self) -> bool:
        if self._plan is None:
            return False
        
        # 再次检查是否符合结果预期
        enviro_narrate_action: Optional[ActorAction] = self._plan.get_action_by_key(EnviroNarrateActionComponent.__name__)
        tag_action: Optional[ActorAction] = self._plan.get_action_by_key(TagActionComponent.__name__)
        if enviro_narrate_action is None or tag_action is None:
            logger.error(f"大模型推理错误 = {self._plan}")
            return False
        
        # 2个结果赋值
        self._result = self._parse_yes(tag_action)
        self._tips = self._parse_tips(enviro_narrate_action)
        return True
###############################################################################################################################################
    def _parse_yes(self, tag_action: ActorAction) -> bool:
        assert tag_action.actionname == TagActionComponent.__name__
        if len(tag_action.values) == 0:
            logger.error(tag_action)
            return False
        return tag_action.values[0].lower() == "yes"
###############################################################################################################################################
    def _parse_tips(self, enviro_narrate_action: ActorAction) -> str:
        assert enviro_narrate_action.actionname == EnviroNarrateActionComponent.__name__
        if len(enviro_narrate_action.values) == 0:
            logger.error(enviro_narrate_action)
            return str(NO_INFO_PROMPT)
        return enviro_narrate_action.single_value()
###############################################################################################################################################


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PreActorChangeStageSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
###############################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(GoToActionComponent): GroupEvent.ADDED}
###############################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GoToActionComponent) and entity.has(ActorComponent) and not entity.has(DeadActionComponent)
###############################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            
            exit_result = self.handle_exit_stage(entity)
            if not exit_result:
                entity.remove(GoToActionComponent)  # 停止离开！
                continue  #?

            enter_result = self.handle_enter_stage(entity)
            if not enter_result:
                entity.remove(GoToActionComponent)  # 停止进入
                continue  #?    

            # 通过了，可以去下一个场景了
            logger.info(f"{self.context.safe_get_entity_name(entity)} 通过了离开和进入条件，可以去下一个场景了")    
###############################################################################################################################################
    def need_check_exit_cond(self, stage_entity: Entity) -> bool:
        if stage_entity.has(StageExitCondStatusComponent):
            return True
        if stage_entity.has(StageExitCondCheckRoleStatusComponent):
            return True
        if stage_entity.has(StageExitCondCheckRolePropsComponent):
            return True
        return False
###############################################################################################################################################
    def need_check_entry_cond(self, stage_entity: Entity) -> bool:
        if stage_entity.has(StageEntryCondStatusComponent):
            return True
        if stage_entity.has(StageEntryCondCheckRoleStatusComponent):
            return True
        if stage_entity.has(StageEntryCondCheckRolePropsComponent):
            return True
        return False
###############################################################################################################################################
    def handle_exit_stage(self, entity: Entity) -> bool:
        #
        current_stage_entity = self.context.safe_get_stage_entity(entity)
        assert current_stage_entity is not None
        if not self.need_check_exit_cond(current_stage_entity):
            return True
        #
        actor_name = self.context.safe_get_entity_name(entity)
        current_stage_name = self.context.safe_get_entity_name(current_stage_entity)
        #
        stage_exit_cond_helper = StageConditionsHelper(f"离开{current_stage_name}的检查所有条件")
        stage_exit_cond_helper.prepare_exit_cond(current_stage_entity, self.context)
        # 准备好数据
        current_role_status_prompt = self.get_role_status_prompt(entity)
        current_role_props_prompt = self.get_role_props_prompt(entity)
        
        
        final_prompt = stage_exit_conditions_check_promt(actor_name, 
                                                         current_stage_name, 
                                                         stage_exit_cond_helper.stage_cond_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_role_status_prompt, 
                                                         current_role_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_role_props_prompt, 
                                                         current_role_props_prompt)

        logger.debug(final_prompt)

        ## 让大模型去推断是否可以离开，分别检查stage自身，角色状态（例如长相），角色道具（拥有哪些道具与文件）
        agent_connect_system = self.context.agent_connect_system
        respones = agent_connect_system.agent_request(current_stage_name, final_prompt)
        if respones is None:
            logger.error("没有回应！！！！！！！！！！！！！")
            return False
        
        logger.debug(f"大模型推理后的结果: {respones}")
        plan = ActorPlan(current_stage_name, respones)
        handle_response_helper = HandleStageConditionsResponseHelper(plan)
        if not handle_response_helper.handle():
            return False
        
        #
        if not handle_response_helper.result:
            # 通知事件
            notify_stage_director(self.context, 
                                  current_stage_entity, 
                                  ActorExitStageFailedBecauseStageRefuse(actor_name, current_stage_name, handle_response_helper.tips))
            return False

        logger.info(f"允许通过！说明如下: {handle_response_helper._tips}")
        ## 可以删除，允许通过！这个上下文就拿掉，不需要了。
        agent_connect_system = self.context.agent_connect_system
        agent_connect_system.remove_last_conversation_between_human_and_ai(current_stage_name)
        return True
###############################################################################################################################################
    def handle_enter_stage(self, entity: Entity) -> bool:
        ##
        target_stage_entity = self.get_target_stage_entity(entity)
        if target_stage_entity is None:
            return False
        
        ##
        if not self.need_check_entry_cond(target_stage_entity):
            return True
        
        ##
        actor_name = self.context.safe_get_entity_name(entity)
        target_stage_name = self.context.safe_get_entity_name(target_stage_entity)
        #
        stage_exit_cond_helper = StageConditionsHelper(f"进入{target_stage_name}的检查所有条件")
        stage_exit_cond_helper.prepare_entry_cond(target_stage_entity, self.context)
        # 准备好数据
        current_role_status_prompt = self.get_role_status_prompt(entity)
        current_role_props_prompt = self.get_role_props_prompt(entity)
        # 最终提示词
        final_prompt = stage_entry_conditions_check_promt(actor_name, 
                                                         target_stage_name, 
                                                         stage_exit_cond_helper.stage_cond_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_role_status_prompt, 
                                                         current_role_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_role_props_prompt, 
                                                         current_role_props_prompt)

        logger.debug(final_prompt)

        ## 让大模型去推断是否可以离开，分别检查stage自身，角色状态（例如长相），角色道具（拥有哪些道具与文件）
        agent_connect_system = self.context.agent_connect_system
        respones = agent_connect_system.agent_request(target_stage_name, final_prompt)
        if respones is None:
            logger.error("没有回应！！！！！！！！！！！！！")
            return False
        
        logger.debug(f"大模型推理后的结果: {respones}")
        plan = ActorPlan(target_stage_name, respones)
        handle_response_helper = HandleStageConditionsResponseHelper(plan)
        if not handle_response_helper.handle():
            return False
        
        if not handle_response_helper.result:
            # 通知事件, 因为没动，得是当前场景需要通知
            current_stage_entity = self.context.safe_get_stage_entity(entity)
            assert current_stage_entity is not None
            notify_stage_director(self.context, 
                                  current_stage_entity, 
                                  ActorEnterStageFailedBecauseStageRefuse(actor_name, target_stage_name, handle_response_helper.tips))
            return False

        logger.info(f"允许通过！说明如下: {handle_response_helper._tips}")
        ## 可以删除，允许通过！这个上下文就拿掉，不需要了。
        agent_connect_system = self.context.agent_connect_system
        agent_connect_system.remove_last_conversation_between_human_and_ai(target_stage_name)
        return True
###############################################################################################################################################
    def get_target_stage_entity(self, entity: Entity) -> Optional[Entity]:
        leave_action_comp: GoToActionComponent = entity.get(GoToActionComponent)
        action: ActorAction = leave_action_comp.action
        if len(action.values) == 0:
            logger.error(leave_action_comp)
            return None
        #
        target_stage_name = action.values[0]
        stageentity = self.context.get_stage_entity(target_stage_name)
        return stageentity
###############################################################################################################################################
    def get_role_status_prompt(self, entity: Entity) -> str:
        safe_name = self.context.safe_get_entity_name(entity)
        role_appearance_comp: AppearanceComponent = entity.get(AppearanceComponent)
        appearance_info: str = role_appearance_comp.appearance
        return role_status_info_when_pre_leave_prompt(safe_name, appearance_info)
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
            prompt_of_props = str(NO_ROLE_PROPS_INFO_PROMPT)
        return prompt_of_props
###############################################################################################################################################