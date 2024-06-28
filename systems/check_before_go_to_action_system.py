from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from systems.components import (GoToActionComponent, 
                        ActorComponent, 
                        StageExitCondStatusComponent,
                        StageExitCondCheckActorStatusComponent,
                        StageExitCondCheckActorPropsComponent,
                        AppearanceComponent,
                        EnviroNarrateActionComponent,
                        TagActionComponent,
                        StageEntryCondStatusComponent,
                        StageEntryCondCheckActorStatusComponent,
                        StageEntryCondCheckActorPropsComponent,
                        DeadActionComponent)
from actor_plan_and_action.actor_action import ActorAction
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from systems.stage_director_component import notify_stage_director
from systems.stage_director_event import IStageDirectorEvent
from builtin_prompt.cn_builtin_prompt import \
            prop_info_prompt, stage_exit_conditions_check_prompt, \
            stage_entry_conditions_check_prompt,\
            exit_stage_failed_beacuse_stage_refuse_prompt, \
            enter_stage_failed_beacuse_stage_refuse_prompt, \
            actor_status_when_stage_change_prompt, \
            go_to_stage_failed_because_stage_is_invalid_prompt, \
            go_to_stage_failed_because_already_in_stage_prompt

from builtin_prompt.cn_constant_prompt import _CNConstantPrompt_
from typing import Optional, cast, override
from systems.check_status_action_system import CheckStatusActionHelper
from actor_plan_and_action.actor_plan import ActorPlan

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorGoToFailedBecauseStageInvalid(IStageDirectorEvent):

    def __init__(self, actor_name: str, stagename: str) -> None:
        self.actor_name = actor_name
        self.stagename = stagename

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self.actor_name:
            # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
            return ""
        return go_to_stage_failed_because_stage_is_invalid_prompt(self.actor_name, self.stagename)
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorGoToFailedBecauseAlreadyInStage(IStageDirectorEvent):

    def __init__(self, actor_name: str, stagename: str) -> None:
        self.actor_name = actor_name
        self.stagename = stagename

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self.actor_name:
            # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
            return ""
        already_in_stage_event = go_to_stage_failed_because_already_in_stage_prompt(self.actor_name, self.stagename)
        return already_in_stage_event
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorExitStageFailedBecauseStageRefuse(IStageDirectorEvent):
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
class ActorEnterStageFailedBecauseStageRefuse(IStageDirectorEvent):
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

    tips: str
    stage_name: str
    stage_cond_status_prompt: str
    cond_check_actor_status_prompt: str
    cond_check_actor_props_prompt: str
     
    def __init__(self, tig: str) -> None:
        self.tips = tig
        self.clear()
####################################################################################################################################
    def clear(self) -> None:
        self.stage_name = ""
        self.stage_cond_status_prompt = str(_CNConstantPrompt_.NONE_PROMPT)
        self.cond_check_actor_status_prompt = str(_CNConstantPrompt_.NONE_PROMPT)
        self.cond_check_actor_props_prompt = str(_CNConstantPrompt_.NONE_PROMPT)
####################################################################################################################################
    def prepare_exit_cond(self, stage_entity: Entity, context: ExtendedContext) -> None:
        self.clear()
        self.stage_name = context.safe_get_entity_name(stage_entity)
        # 准备好数据
        if stage_entity.has(StageExitCondStatusComponent):
            self.stage_cond_status_prompt = cast(StageExitCondStatusComponent, stage_entity.get(StageExitCondStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageExitCondCheckActorStatusComponent):
            self.cond_check_actor_status_prompt = cast(StageExitCondCheckActorStatusComponent, stage_entity.get(StageExitCondCheckActorStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageExitCondCheckActorPropsComponent):
            self.cond_check_actor_props_prompt = cast(StageExitCondCheckActorPropsComponent, stage_entity.get(StageExitCondCheckActorPropsComponent)).condition
####################################################################################################################################
    def prepare_entry_cond(self, stage_entity: Entity, context: ExtendedContext) -> None:
        self.clear()
        self.stage_name = context.safe_get_entity_name(stage_entity)
        # 准备好数据
        if stage_entity.has(StageEntryCondStatusComponent):
            self.stage_cond_status_prompt = cast(StageEntryCondStatusComponent, stage_entity.get(StageEntryCondStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageEntryCondCheckActorStatusComponent):
            self.cond_check_actor_status_prompt = cast(StageEntryCondCheckActorStatusComponent, stage_entity.get(StageEntryCondCheckActorStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageEntryCondCheckActorPropsComponent):
            self.cond_check_actor_props_prompt = cast(StageEntryCondCheckActorPropsComponent, stage_entity.get(StageEntryCondCheckActorPropsComponent)).condition
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################

class HandleStageConditionsResponseHelper:
    def __init__(self, plan: ActorPlan) -> None:
        self._plan = plan
        self._result = False
        self._tips = str(_CNConstantPrompt_.NONE_PROMPT)
###############################################################################################################################################
    @property
    def result(self) -> bool:
        return self._result
###############################################################################################################################################
    @property
    def tips(self) -> str:
        return self._tips
###############################################################################################################################################
    def parse(self) -> bool:
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
        assert tag_action._action_name == TagActionComponent.__name__
        return tag_action.bool_value(0)
        # if len(tag_action._values) == 0:
        #     logger.error(tag_action)
        #     return False
        # return tag_action._values[0].lower() == "yes"
###############################################################################################################################################
    def _parse_tips(self, enviro_narrate_action: ActorAction) -> str:
        assert enviro_narrate_action._action_name == EnviroNarrateActionComponent.__name__
        if len(enviro_narrate_action._values) == 0:
            logger.error(enviro_narrate_action)
            return str(_CNConstantPrompt_.NONE_PROMPT)
        return enviro_narrate_action.join_values()
###############################################################################################################################################


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class CheckBeforeGoToActionSystem(ReactiveProcessor):

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

            # 检查目标场景是否有效，可能是无效的，例如不存在，或者已经在目标场景了
            if not self.check_target_stage_is_valid(entity):
                self.on_failed(entity)
                continue
            
            # 检查离开当前场景的条件是否满足，需要LLM推理
            exit_result = self.handle_exit_stage_with_conditions(entity)
            if not exit_result:
                self.on_failed(entity)
                continue
            
            # 检查进入目标场景的条件是否满足，需要LLM推理
            enter_result = self.handle_enter_stage_with_conditions(entity)
            if not enter_result:
                self.on_failed(entity)
                continue 

            # 通过了，可以去下一个场景了
            logger.info(f"{self.context.safe_get_entity_name(entity)} 通过了离开和进入条件，可以去下一个场景了")    
###############################################################################################################################################
    def check_target_stage_is_valid(self, entity: Entity) -> bool:
        current_stage_entity = self.context.safe_get_stage_entity(entity)
        #assert current_stage_entity is not None
        if current_stage_entity is None:
            logger.error("当前场景为空??????！！！！！！！！！！！！！")
            return False
    
        safe_name = self.context.safe_get_entity_name(entity)

        target_stage_name = self.get_target_stage_name(entity)
        target_stage_entity = self.get_target_stage_entity(entity)
        if target_stage_entity is None:
            notify_stage_director(self.context, 
                                  current_stage_entity, 
                                  ActorGoToFailedBecauseStageInvalid(safe_name, target_stage_name))
            return False

        if current_stage_entity == target_stage_entity:
            notify_stage_director(self.context, 
                                  current_stage_entity, 
                                  ActorGoToFailedBecauseAlreadyInStage(safe_name, target_stage_name))
            return False

        return True
###############################################################################################################################################
    def need_check_exit_cond(self, stage_entity: Entity) -> bool:
        if stage_entity.has(StageExitCondStatusComponent):
            return True
        if stage_entity.has(StageExitCondCheckActorStatusComponent):
            return True
        if stage_entity.has(StageExitCondCheckActorPropsComponent):
            return True
        return False
###############################################################################################################################################
    def need_check_entry_cond(self, stage_entity: Entity) -> bool:
        if stage_entity.has(StageEntryCondStatusComponent):
            return True
        if stage_entity.has(StageEntryCondCheckActorStatusComponent):
            return True
        if stage_entity.has(StageEntryCondCheckActorPropsComponent):
            return True
        return False
###############################################################################################################################################
    def handle_exit_stage_with_conditions(self, entity: Entity) -> bool:
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
        current_actor_status_prompt = self.get_actor_status_prompt(entity)
        current_actor_props_prompt = self.get_actor_props_prompt(entity)
        
        
        final_prompt = stage_exit_conditions_check_prompt(actor_name, 
                                                         current_stage_name, 
                                                         stage_exit_cond_helper.stage_cond_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_actor_status_prompt, 
                                                         current_actor_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_actor_props_prompt, 
                                                         current_actor_props_prompt)

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
        if not handle_response_helper.parse():
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
    def handle_enter_stage_with_conditions(self, entity: Entity) -> bool:
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
        current_actor_status_prompt = self.get_actor_status_prompt(entity)
        current_actor_props_prompt = self.get_actor_props_prompt(entity)
        # 最终提示词
        final_prompt = stage_entry_conditions_check_prompt(actor_name, 
                                                         target_stage_name, 
                                                         stage_exit_cond_helper.stage_cond_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_actor_status_prompt, 
                                                         current_actor_status_prompt, 
                                                         stage_exit_cond_helper.cond_check_actor_props_prompt, 
                                                         current_actor_props_prompt)

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
        if not handle_response_helper.parse():
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
        target_stage_name = self.get_target_stage_name(entity)
        return self.context.get_stage_entity(target_stage_name)
###############################################################################################################################################
    def get_target_stage_name(self, entity: Entity) -> str:
        go_to_action_comp: GoToActionComponent = entity.get(GoToActionComponent)
        action: ActorAction = go_to_action_comp.action
        return action.value(0)
        # if len(action._values) == 0:
        #     logger.error(go_to_action_comp)
        #     return ""
        # return action._values[0]
###############################################################################################################################################
    # todo 目前就把外观信息当作状态信息，后续可以加入更多的状态信息
    def get_actor_status_prompt(self, entity: Entity) -> str:
        safe_name = self.context.safe_get_entity_name(entity)
        appearance_comp: AppearanceComponent = entity.get(AppearanceComponent)
        appearance_info: str = appearance_comp.appearance
        return actor_status_when_stage_change_prompt(safe_name, appearance_info)
###############################################################################################################################################
    def get_actor_props_prompt(self, entity: Entity) -> str:
        helper = CheckStatusActionHelper(self.context)
        helper.check_status(entity)
        props = helper.props + helper.special_components
        prompt_of_props = ""
        if len(props) > 0:
            for prop in props:
                prompt_of_props += prop_info_prompt(prop, True, True)
        else:
            prompt_of_props = str(_CNConstantPrompt_.NO_ACTOR_PROPS_PROMPT)
        return prompt_of_props
###############################################################################################################################################
    def on_failed(self, entity: Entity) -> None:
        if entity.has(GoToActionComponent):
            entity.remove(GoToActionComponent)
###############################################################################################################################################