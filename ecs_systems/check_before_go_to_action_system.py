from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from ecs_systems.action_components import (GoToAction, 
                        StageNarrateAction,
                        TagAction,
                        DeadAction)

from ecs_systems.components import (
    ActorComponent, 
    StageExitCondStatusComponent,
    StageExitCondCheckActorStatusComponent,
    StageExitCondCheckActorPropsComponent,
    AppearanceComponent,
    StageEntryCondStatusComponent,
    StageEntryCondCheckActorStatusComponent,
    StageEntryCondCheckActorPropsComponent,
)

from my_agent.agent_action import AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from ecs_systems.stage_director_component import StageDirectorComponent
from ecs_systems.stage_director_event import IStageDirectorEvent
from ecs_systems.cn_builtin_prompt import \
            prop_prompt, stage_exit_conditions_check_prompt, \
            stage_entry_conditions_check_prompt,\
            exit_stage_failed_beacuse_stage_refuse_prompt, \
            enter_stage_failed_beacuse_stage_refuse_prompt, \
            actor_status_when_stage_change_prompt, \
            go_to_stage_failed_because_stage_is_invalid_prompt, \
            go_to_stage_failed_because_already_in_stage_prompt

from ecs_systems.cn_constant_prompt import _CNConstantPrompt_
from typing import Optional, cast, override
from ecs_systems.check_status_action_system import CheckStatusActionHelper
from my_agent.agent_plan import AgentPlan

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorGoToFailedBecauseStageInvalid(IStageDirectorEvent):

    def __init__(self, actor_name: str, stage_name: str) -> None:
        self._actor_name: str = actor_name
        self._stage_name: str = stage_name

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._actor_name:
            # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
            return ""
        return go_to_stage_failed_because_stage_is_invalid_prompt(self._actor_name, self._stage_name)
    
    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorGoToFailedBecauseAlreadyInStage(IStageDirectorEvent):

    def __init__(self, actor_name: str, stage_name: str) -> None:
        self._actor_name: str = actor_name
        self._stage_name: str = stage_name

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._actor_name:
            # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
            return ""
        return go_to_stage_failed_because_already_in_stage_prompt(self._actor_name, self._stage_name)
    
    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorExitStageFailedBecauseStageRefuse(IStageDirectorEvent):
    def __init__(self, actor_name: str, stage_name: str, tips: str) -> None:
        self._actor_name: str = actor_name
        self._stage_name: str = stage_name
        self._tips: str = tips

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._actor_name:
            return ""
        return exit_stage_failed_beacuse_stage_refuse_prompt(self._actor_name, self._stage_name, self._tips)
    
    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorEnterStageFailedBecauseStageRefuse(IStageDirectorEvent):
    def __init__(self, actor_name: str, stage_name: str, tips: str) -> None:
        self._actor_name: str = actor_name
        self._stage_name: str = stage_name
        self._tips: str = tips

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._actor_name:
            return ""
        return enter_stage_failed_beacuse_stage_refuse_prompt(self._actor_name, self._stage_name, self._tips)
    
    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class StageConditionsHelper:

    _tips: str
    _stage_name: str
    _stage_cond_status_prompt: str
    _cond_check_actor_status_prompt: str
    _cond_check_actor_props_prompt: str
     
    def __init__(self, tig: str) -> None:
        self._tips = tig
        self.clear()
####################################################################################################################################
    def clear(self) -> None:
        self._stage_name = ""
        self._stage_cond_status_prompt = str(_CNConstantPrompt_.NONE_PROMPT)
        self._cond_check_actor_status_prompt = str(_CNConstantPrompt_.NONE_PROMPT)
        self._cond_check_actor_props_prompt = str(_CNConstantPrompt_.NONE_PROMPT)
####################################################################################################################################
    def prepare_exit_cond(self, stage_entity: Entity, context: RPGEntitasContext) -> None:
        self.clear()
        self._stage_name = context.safe_get_entity_name(stage_entity)
        # 准备好数据
        if stage_entity.has(StageExitCondStatusComponent):
            self._stage_cond_status_prompt = cast(StageExitCondStatusComponent, stage_entity.get(StageExitCondStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageExitCondCheckActorStatusComponent):
            self._cond_check_actor_status_prompt = cast(StageExitCondCheckActorStatusComponent, stage_entity.get(StageExitCondCheckActorStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageExitCondCheckActorPropsComponent):
            self._cond_check_actor_props_prompt = cast(StageExitCondCheckActorPropsComponent, stage_entity.get(StageExitCondCheckActorPropsComponent)).condition
####################################################################################################################################
    def prepare_entry_cond(self, stage_entity: Entity, context: RPGEntitasContext) -> None:
        self.clear()
        self._stage_name = context.safe_get_entity_name(stage_entity)
        # 准备好数据
        if stage_entity.has(StageEntryCondStatusComponent):
            self._stage_cond_status_prompt = cast(StageEntryCondStatusComponent, stage_entity.get(StageEntryCondStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageEntryCondCheckActorStatusComponent):
            self._cond_check_actor_status_prompt = cast(StageEntryCondCheckActorStatusComponent, stage_entity.get(StageEntryCondCheckActorStatusComponent)).condition
        # 准备好数据
        if stage_entity.has(StageEntryCondCheckActorPropsComponent):
            self._cond_check_actor_props_prompt = cast(StageEntryCondCheckActorPropsComponent, stage_entity.get(StageEntryCondCheckActorPropsComponent)).condition
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################

class HandleStageConditionsResponseHelper:
    def __init__(self, plan: AgentPlan) -> None:
        self._plan: AgentPlan = plan
        self._result: bool = False
        self._tips: str = str(_CNConstantPrompt_.NONE_PROMPT)
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
        enviro_narrate_action: Optional[AgentAction] = self._plan.get_action_by_key(StageNarrateAction.__name__)
        tag_action: Optional[AgentAction] = self._plan.get_action_by_key(TagAction.__name__)
        if enviro_narrate_action is None or tag_action is None:
            logger.error(f"大模型推理错误 = {self._plan}")
            return False
        
        # 2个结果赋值
        self._result = self._parse_yes(tag_action)
        self._tips = self._parse_tips(enviro_narrate_action)
        return True
###############################################################################################################################################
    def _parse_yes(self, tag_action: AgentAction) -> bool:
        assert tag_action._action_name == TagAction.__name__
        return tag_action.bool_value(0)
###############################################################################################################################################
    def _parse_tips(self, enviro_narrate_action: AgentAction) -> str:
        #assert enviro_narrate_action._action_name == StageNarrateAction.__name__
        if len(enviro_narrate_action._values) == 0:
            logger.error(enviro_narrate_action)
            return str(_CNConstantPrompt_.NONE_PROMPT)
        return enviro_narrate_action.join_values()
###############################################################################################################################################


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class CheckBeforeGoToActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context = context
###############################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(GoToAction): GroupEvent.ADDED}
###############################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GoToAction) and entity.has(ActorComponent) and not entity.has(DeadAction)
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
            logger.info(f"{self._context.safe_get_entity_name(entity)} 通过了离开和进入条件，可以去下一个场景了")    
###############################################################################################################################################
    def check_target_stage_is_valid(self, entity: Entity) -> bool:
        current_stage_entity = self._context.safe_get_stage_entity(entity)
        #assert current_stage_entity is not None
        if current_stage_entity is None:
            logger.error("当前场景为空??????！！！！！！！！！！！！！")
            return False
    
        safe_name = self._context.safe_get_entity_name(entity)

        target_stage_name = self.get_target_stage_name(entity)
        target_stage_entity = self.get_target_stage_entity(entity)
        if target_stage_entity is None:
            StageDirectorComponent.add_event_to_stage_director(self._context, 
                                  current_stage_entity, 
                                  ActorGoToFailedBecauseStageInvalid(safe_name, target_stage_name))
            return False

        if current_stage_entity == target_stage_entity:
            StageDirectorComponent.add_event_to_stage_director(self._context, 
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
        current_stage_entity = self._context.safe_get_stage_entity(entity)
        assert current_stage_entity is not None
        if not self.need_check_exit_cond(current_stage_entity):
            return True
        #
        actor_name = self._context.safe_get_entity_name(entity)
        current_stage_name = self._context.safe_get_entity_name(current_stage_entity)
        #
        stage_exit_cond_helper = StageConditionsHelper(f"离开{current_stage_name}的检查所有条件")
        stage_exit_cond_helper.prepare_exit_cond(current_stage_entity, self._context)
        # 准备好数据
        current_actor_status_prompt = self.get_actor_status_prompt(entity)
        current_actor_props_prompt = self.get_actor_props_prompt(entity)
        
        
        final_prompt = stage_exit_conditions_check_prompt(actor_name, 
                                                         current_stage_name, 
                                                         stage_exit_cond_helper._stage_cond_status_prompt, 
                                                         stage_exit_cond_helper._cond_check_actor_status_prompt, 
                                                         current_actor_status_prompt, 
                                                         stage_exit_cond_helper._cond_check_actor_props_prompt, 
                                                         current_actor_props_prompt)

        logger.debug(final_prompt)

        ## 让大模型去推断是否可以离开，分别检查stage自身，角色状态（例如长相），角色道具（拥有哪些道具与文件）
        agent_request = self._context._langserve_agent_system.create_agent_request_task(current_stage_name, final_prompt)
        if agent_request is None:
            logger.error("agent_request is None")
            return False
        
        response = agent_request.request()
        #respones = langserve_agent_system.agent_request(current_stage_name, final_prompt)
        if response is None:
            logger.error("没有回应！！！！！！！！！！！！！")
            return False
        
        logger.debug(f"大模型推理后的结果: {response}")
        plan = AgentPlan(current_stage_name, response)
        handle_response_helper = HandleStageConditionsResponseHelper(plan)
        if not handle_response_helper.parse():
            return False
        
        #
        if not handle_response_helper.result:
            # 通知事件
            StageDirectorComponent.add_event_to_stage_director(self._context, 
                                  current_stage_entity, 
                                  ActorExitStageFailedBecauseStageRefuse(actor_name, current_stage_name, handle_response_helper.tips))
            return False

        logger.info(f"允许通过！说明如下: {handle_response_helper._tips}")
        ## 可以删除，允许通过！这个上下文就拿掉，不需要了。
        self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(current_stage_name)
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
        actor_name = self._context.safe_get_entity_name(entity)
        target_stage_name = self._context.safe_get_entity_name(target_stage_entity)
        #
        stage_exit_cond_helper = StageConditionsHelper(f"进入{target_stage_name}的检查所有条件")
        stage_exit_cond_helper.prepare_entry_cond(target_stage_entity, self._context)
        # 准备好数据
        current_actor_status_prompt = self.get_actor_status_prompt(entity)
        current_actor_props_prompt = self.get_actor_props_prompt(entity)
        # 最终提示词
        final_prompt = stage_entry_conditions_check_prompt(actor_name, 
                                                         target_stage_name, 
                                                         stage_exit_cond_helper._stage_cond_status_prompt, 
                                                         stage_exit_cond_helper._cond_check_actor_status_prompt, 
                                                         current_actor_status_prompt, 
                                                         stage_exit_cond_helper._cond_check_actor_props_prompt, 
                                                         current_actor_props_prompt)

        logger.debug(final_prompt)

        ## 让大模型去推断是否可以离开，分别检查stage自身，角色状态（例如长相），角色道具（拥有哪些道具与文件）
        agent_request = self._context._langserve_agent_system.create_agent_request_task(target_stage_name, final_prompt)
        if agent_request is None:
            logger.error("agent_request is None")
            return False
        
        response = agent_request.request()
        #response = langserve_agent_system.agent_request(target_stage_name, final_prompt)
        if response is None:
            logger.error("没有回应！！！！！！！！！！！！！")
            return False
        
        logger.debug(f"大模型推理后的结果: {response}")
        plan = AgentPlan(target_stage_name, response)
        handle_response_helper = HandleStageConditionsResponseHelper(plan)
        if not handle_response_helper.parse():
            return False
        
        if not handle_response_helper.result:
            # 通知事件, 因为没动，得是当前场景需要通知
            current_stage_entity = self._context.safe_get_stage_entity(entity)
            assert current_stage_entity is not None
            StageDirectorComponent.add_event_to_stage_director(self._context, 
                                  current_stage_entity, 
                                  ActorEnterStageFailedBecauseStageRefuse(actor_name, target_stage_name, handle_response_helper.tips))
            return False

        logger.info(f"允许通过！说明如下: {handle_response_helper._tips}")
        ## 可以删除，允许通过！这个上下文就拿掉，不需要了。
        self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(target_stage_name)
        return True
###############################################################################################################################################
    def get_target_stage_entity(self, entity: Entity) -> Optional[Entity]:
        target_stage_name = self.get_target_stage_name(entity)
        return self._context.get_stage_entity(target_stage_name)
###############################################################################################################################################
    def get_target_stage_name(self, entity: Entity) -> str:
        go_to_action_comp: GoToAction = entity.get(GoToAction)
        action: AgentAction = go_to_action_comp.action
        return action.value(0)
###############################################################################################################################################
    # todo 目前就把角色外观信息当作状态信息，后续可以加入更多的状态信息
    def get_actor_status_prompt(self, entity: Entity) -> str:
        safe_name = self._context.safe_get_entity_name(entity)
        appearance_comp = entity.get(AppearanceComponent)
        return actor_status_when_stage_change_prompt(safe_name, cast(str, appearance_comp.appearance))
###############################################################################################################################################
    def get_actor_props_prompt(self, entity: Entity) -> str:
        helper = CheckStatusActionHelper(self._context)
        helper.check_status(entity)
        props = helper._prop_files_as_weapon_clothes_non_consumable_item + helper._prop_files_as_special_components
        prompt_of_props = ""
        if len(props) > 0:
            for prop in props:
                prompt_of_props += prop_prompt(prop, True, True)
        else:
            prompt_of_props = str(_CNConstantPrompt_.NO_ACTOR_PROPS_PROMPT)
        return prompt_of_props
###############################################################################################################################################
    def on_failed(self, entity: Entity) -> None:
        if entity.has(GoToAction):
            entity.remove(GoToAction)
###############################################################################################################################################