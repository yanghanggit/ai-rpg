from entitas import Entity, Matcher, ReactiveProcessor # type: ignore
from typing import Optional, override
from loguru import logger
from auxiliary.actor_plan_and_action import ActorAction
from auxiliary.components import (UsePropActionComponent, StageExitCondStatusComponent, 
                                  EnviroNarrateActionComponent, StageComponent, ActorComponent,
                                  DeadActionComponent)
from auxiliary.target_and_message_format_handle import parse_target_and_message
from my_entitas.extended_context import ExtendedContext
from auxiliary.director_component import notify_stage_director
from entitas.group import GroupEvent
from auxiliary.director_event import IDirectorEvent
from builtin_prompt.cn_builtin_prompt import prop_info_prompt, use_prop_to_stage_prompt, __ConstantPromptValue__, use_prop_no_response_prompt
from auxiliary.actor_plan_and_action import ActorPlan
from auxiliary.target_and_message_format_handle import use_prop_check, ErrorUsePropEnable
from file_system.files_def import PropFile


# 通知导演的类
class ActorUsePropToStageEvent(IDirectorEvent):
    def __init__(self, actor_name: str, targetname: str, propname: str, tips: str) -> None:
        self.actor_name = actor_name
        self.targetname = targetname
        self.propname = propname
        self.tips = tips

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self.actor_name:
            return ""
        return self.tips
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
# 帮助分析给用户的提示。因为提示是在一个动作里，所以这个类是一个辅助类
class UsePropResponseHelper:

    def __init__(self, plan: ActorPlan) -> None:
        self._plan = plan
        self._tips =  self._parse(self._plan)
        logger.debug(f"UseInteractivePropHelper: {self._tips}")

    def _parse(self, plan: ActorPlan) -> str:
        enviro_narrate_action: Optional[ActorAction] = plan.get_action_by_key(EnviroNarrateActionComponent.__name__)
        if enviro_narrate_action is None or len(enviro_narrate_action.values) == 0:
           logger.error(f"InteractivePropActionSystem: {plan._raw} is not correct")
           return ""
        return enviro_narrate_action.single_value()
    
    @property
    def tips(self) -> str:
        return self._tips
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class UsePropActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
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
            self.useprop(entity)
####################################################################################################################################
    # 核心处理代码
    def useprop(self, entity: Entity) -> None:

        context = self.context
        filesystem = context.file_system
        use_interactive_prop_comp: UsePropActionComponent = entity.get(UsePropActionComponent)
        action: ActorAction = use_interactive_prop_comp.action

        for value in action.values:
            # 传入参数是否合理？
            parse = parse_target_and_message(value)
            targetname: Optional[str] = parse[0]
            propname: Optional[str] = parse[1]
            if targetname is None or propname is None:
                logger.warning(f"InteractivePropActionSystem: {value} is not correct")
                continue

            # 基本检查，是否发起与接受的对象是合理的，而且是否在一个场景里
            error_code = use_prop_check(context, entity, targetname)
            if error_code != ErrorUsePropEnable.VALID:
                logger.error(f"检查场景关系失败，错误码：{error_code}")
                continue
            
            # 检查道具是否存在，需要提醒，如果没有是大问题
            prop_file = filesystem.get_prop_file(action.name, propname)
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
        assert prop_file._prop.is_weapon() or prop_file._prop.is_non_consumable_item()
        assert entity.has(ActorComponent)
        assert target_entity.has(StageComponent)
        
        context = self.context
        targetname = context.safe_get_entity_name(target_entity)
        username = context.safe_get_entity_name(entity)
        assert context.file_system.get_prop_file(username, prop_file._name) is not None

        # 检查条件
        exit_cond_status_prompt = str(__ConstantPromptValue__.NONE_PROMPT)
        if target_entity.has(StageExitCondStatusComponent):
            stage_exit_cond_status_comp: StageExitCondStatusComponent = target_entity.get(StageExitCondStatusComponent)
            exit_cond_status_prompt = stage_exit_cond_status_comp.condition
        else:
            logger.warning(f"InteractivePropActionSystem: {targetname} 没有退出条件, 下面的不用走")
            notify_stage_director(context, entity, ActorUsePropToStageEvent(username, 
                                                                                     targetname, 
                                                                                     prop_file._name, 
                                                                                     use_prop_no_response_prompt(username, prop_file._name, targetname)))
            return True

        # 道具的提示词
        prop_prompt = prop_info_prompt(prop_file._prop)

        # 包装的最终提示词
        final_prompt = use_prop_to_stage_prompt(username, prop_file._name, prop_prompt, exit_cond_status_prompt)

        # 准备提交请求
        logger.debug(f"InteractivePropActionSystem, {targetname}: {final_prompt}")
        agent_connect_system = context.agent_connect_system
        # 用同步的接口，这样能知道结果应该通知给谁。
        response = agent_connect_system.agent_request(targetname, final_prompt)
        if response is not None:
            # 场景有反应
            logger.debug(f"InteractivePropActionSystem: {response}")
            # 组织一下数据
            plan = ActorPlan(targetname, response)
            helper = UsePropResponseHelper(plan)
            if helper.tips != "":
                # 还是要做防守与通知导演
                notify_stage_director(context, entity, ActorUsePropToStageEvent(username, targetname, prop_file._name, helper.tips))
            else:
                logger.warning(f"是空的？怎么回事？")
        else:
            logger.debug(f"InteractivePropActionSystem: 没有收到回复")

        # 最终返回
        return True
###################################################################################################################