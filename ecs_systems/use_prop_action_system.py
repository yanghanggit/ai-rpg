from entitas import Entity, Matcher, ReactiveProcessor # type: ignore
from typing import Optional, override
from loguru import logger
from my_agent.agent_action import AgentAction
from ecs_systems.action_components import (UsePropActionComponent, EnviroNarrateActionComponent, DeadActionComponent)
from ecs_systems.components import StageComponent, ActorComponent, StageExitCondStatusComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from ecs_systems.stage_director_component import StageDirectorComponent
from entitas.group import GroupEvent
from ecs_systems.stage_director_event import IStageDirectorEvent
from ecs_systems.cn_builtin_prompt import prop_prompt, use_prop_to_stage_prompt, use_prop_no_response_prompt
from ecs_systems.cn_constant_prompt import _CNConstantPrompt_
from my_agent.agent_plan import AgentPlan
from gameplay_checks.use_prop_check import use_prop_check, ErrorUsePropEnable
from file_system.files_def import PropFile


# 通知导演的类
class ActorUsePropToStageEvent(IStageDirectorEvent):
    def __init__(self, actor_name: str, target_name: str, prop_name: str, tips: str) -> None:
        self._actor_name: str = actor_name
        self._target_name: str = target_name
        self._prop_name: str = prop_name
        self._tips: str = tips

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._actor_name:
            return ""
        return self._tips
    
    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        if self._target_name != stage_name:
            return ""
        return self._tips
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
# 帮助分析给用户的提示。因为提示是在一个动作里，所以这个类是一个辅助类
class UsePropResponseHelper:

    def __init__(self, plan: AgentPlan) -> None:
        self._plan = plan
        self._tips =  self._parse(self._plan)
        logger.debug(f"UseInteractivePropHelper: {self._tips}")

    def _parse(self, plan: AgentPlan) -> str:
        enviro_narrate_action: Optional[AgentAction] = plan.get_action_by_key(EnviroNarrateActionComponent.__name__)
        if enviro_narrate_action is None or len(enviro_narrate_action._values) == 0:
           logger.error(f"InteractivePropActionSystem: {plan._raw} is not correct")
           return ""
        return enviro_narrate_action.join_values()
    
    @property
    def tips(self) -> str:
        return self._tips
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class UsePropActionSystem(ReactiveProcessor):
    def __init__(self, context: RPGEntitasContext):
        super().__init__(context)
        self._context = context
####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(UsePropActionComponent): GroupEvent.ADDED }
####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(UsePropActionComponent) and entity.has(ActorComponent) and not entity.has(DeadActionComponent)
####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.use_prop(entity)
####################################################################################################################################
    # 核心处理代码
    def use_prop(self, entity: Entity) -> None:

        context = self._context
        use_interactive_prop_comp: UsePropActionComponent = entity.get(UsePropActionComponent)
        action: AgentAction = use_interactive_prop_comp.action
        target_and_message = action.target_and_message_values()
        for tp in target_and_message:
            targetname = tp[0]
            propname = tp[1]
            # 基本检查，是否发起与接受的对象是合理的，而且是否在一个场景里
            error_code = use_prop_check(context, entity, targetname)
            if error_code != ErrorUsePropEnable.VALID:
                logger.error(f"检查场景关系失败，错误码：{error_code}")
                continue
            
            # 检查道具是否存在，需要提醒，如果没有是大问题
            prop_file = context._file_system.get_prop_file(action._actor_name, propname)
            if prop_file is None:
                logger.error(f"检查道具合理性失败，{propname} 不存在")
                continue
            
            # 目前只处理场景
            is_stage_entity = context.get_stage_entity(targetname)
            if is_stage_entity is not None:
                assert is_stage_entity.has(StageComponent)
                if not self.use_prop_to_stage(entity, is_stage_entity, prop_file):
                    logger.error(f"对场景 {targetname} 使用道具 {propname} 失败？")
                    continue
            else:
                logger.warning(f"{targetname} 不是一个场景，当前版本暂不处理")     
                continue
###################################################################################################################
    def use_prop_to_stage(self, entity: Entity, target_entity: Entity, prop_file: PropFile) -> bool:
        # 目前应该是这些！！
        #assert prop_file._prop_model.is_weapon() or prop_file._prop_model.is_non_consumable_item()
        assert entity.has(ActorComponent)
        assert target_entity.has(StageComponent)
        
        context = self._context
        targetname = context.safe_get_entity_name(target_entity)
        username = context.safe_get_entity_name(entity)
        assert context._file_system.get_prop_file(username, prop_file._name) is not None

        # 检查条件
        exit_cond_status_prompt = str(_CNConstantPrompt_.NONE_PROMPT)
        if target_entity.has(StageExitCondStatusComponent):
            stage_exit_cond_status_comp: StageExitCondStatusComponent = target_entity.get(StageExitCondStatusComponent)
            exit_cond_status_prompt = stage_exit_cond_status_comp.condition
        else:
            logger.warning(f"InteractivePropActionSystem: {targetname} 没有退出条件, 下面的不用走")
            StageDirectorComponent.add_event_to_stage_director(context, entity, ActorUsePropToStageEvent(username, 
                                                                                     targetname, 
                                                                                     prop_file._name, 
                                                                                     use_prop_no_response_prompt(username, prop_file._name, targetname)))
            return True

        # 道具的提示词
        prop_prompt = prop_prompt(prop_file, True, True)

        # 包装的最终提示词
        final_prompt = use_prop_to_stage_prompt(username, prop_file._name, prop_prompt, exit_cond_status_prompt)

        # 准备提交请求
        logger.debug(f"InteractivePropActionSystem, {targetname}: {final_prompt}")
        agent_request = context._langserve_agent_system.create_agent_request_task(targetname, final_prompt)
        if agent_request is None:
            logger.error(f"InteractivePropActionSystem: {targetname} request error.")
            return False

        # 用同步的接口，这样能知道结果应该通知给谁。
        response = agent_request.request()
        #response = langserve_agent_system.agent_request(targetname, final_prompt)
        if response is not None:
            # 场景有反应
            logger.debug(f"InteractivePropActionSystem: {response}")
            # 组织一下数据
            plan = AgentPlan(targetname, response)
            helper = UsePropResponseHelper(plan)
            if helper.tips != "":
                # 还是要做防守与通知导演
                StageDirectorComponent.add_event_to_stage_director(context, entity, ActorUsePropToStageEvent(username, targetname, prop_file._name, helper.tips))
            else:
                logger.warning(f"是空的？怎么回事？")
        else:
            logger.debug(f"InteractivePropActionSystem: 没有收到回复")

        # 最终返回
        return True
###################################################################################################################