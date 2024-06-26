from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (
    GoToActionComponent, 
    ActorComponent,
    DeadActionComponent,
    PerceptionActionComponent)
from auxiliary.actor_plan_and_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import notify_stage_director
from typing import cast, override, List
from auxiliary.director_event import IDirectorEvent
from systems.director_system import director_events_to_actor
from builtin_prompt.cn_builtin_prompt import ( leave_stage_prompt,
                                          enter_stage_prompt1,
                                          enter_stage_prompt2)

###############################################################################################################################################
class GoToActionHelper:

    def __init__(self, context: ExtendedContext, who: Entity, target_stage_name: str) -> None:
        self.context = context
        self.who = who
        self.current_stage_name = cast(ActorComponent, who.get(ActorComponent)).current_stage
        self.current_stage_entity = self.context.get_stage_entity(self.current_stage_name)
        self.target_stage_name = target_stage_name
        self.target_stage_entity = self.context.get_stage_entity(target_stage_name)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorLeaveStageEvent(IDirectorEvent):

    def __init__(self, actor_name: str, current_stage_name: str, goto_stage_name: str) -> None:
        self.actor_name = actor_name
        self.current_stage_name = current_stage_name
        self.goto_stage_name = goto_stage_name

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        event = leave_stage_prompt(self.actor_name, self.current_stage_name, self.goto_stage_name)
        return event
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = leave_stage_prompt(self.actor_name, self.current_stage_name, self.goto_stage_name)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorEnterStageEvent(IDirectorEvent):

    def __init__(self, actor_name: str, stage_name: str, last_stage_name: str) -> None:
        self.actor_name = actor_name
        self.stage_name = stage_name
        self.last_stage_name = last_stage_name

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self.actor_name:
            # 目标场景内的一切听到的是这个:"xxx进入了场景"
            return enter_stage_prompt1(self.actor_name, self.stage_name)
            
        #通知我自己，我从哪里去往了哪里。这样prompt更加清晰一些
        return enter_stage_prompt2(self.actor_name, self.stage_name, self.last_stage_name)
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = enter_stage_prompt1(self.actor_name, self.stage_name)
        return event    
####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class GoToActionSystem(ReactiveProcessor):

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
        self._handle(entities)
###############################################################################################################################################
    def _handle(self, entities: List[Entity]) -> None:

        for entity in entities:
            if not entity.has(ActorComponent):
                logger.warning(f"GoToActionSystem: {entity} is not Actor?!")
                continue
            
            go_to_action_comp: GoToActionComponent = entity.get(GoToActionComponent)
            action: ActorAction = go_to_action_comp.action
            if len(action.values) == 0:
               continue
   
            stagename = action.values[0]
            handle = GoToActionHelper(self.context, entity, stagename)
            if handle.target_stage_entity is None or handle.current_stage_entity is None or handle.target_stage_entity == handle.current_stage_entity:
                continue

            if handle.current_stage_entity is not None:
                #离开前的处理
                self.before_leave_stage(handle)
                #离开
                self.leave_stage(handle)

            #进入新的场景
            self.enter_stage(handle)
            #进入场景后的处理
            self.after_enter_stage(handle)
###############################################################################################################################################            
    def enter_stage(self, helper: GoToActionHelper) -> None:

        entity = helper.who
        current_stage_name = helper.current_stage_name
        target_stage_name = helper.target_stage_name
        target_stage_entity = helper.target_stage_entity
        assert target_stage_entity is not None
        actor_comp: ActorComponent = entity.get(ActorComponent)

        replace_name = actor_comp.name
        replace_current_stage = target_stage_name
        entity.replace(ActorComponent, replace_name, replace_current_stage)
        self.context.change_stage_tag_component(entity, current_stage_name, replace_current_stage)

        #进入场景的事件需要通知相关的人
        notify_stage_director(self.context, entity, ActorEnterStageEvent(actor_comp.name, target_stage_name, current_stage_name))
###############################################################################################################################################
    def before_leave_stage(self, helper: GoToActionHelper) -> None:
        #目前就是强行刷一下history
        self.direct_before_leave(helper)
###############################################################################################################################################
    def direct_before_leave(self, helper: GoToActionHelper) -> None:
        director_events_to_actor(self.context, helper.who)
###############################################################################################################################################
    def leave_stage(self, helper: GoToActionHelper) -> None:
        entity: Entity = helper.who
        actor_comp: ActorComponent = entity.get(ActorComponent)
        assert helper.current_stage_entity is not None

        # 必须在场景信息还有效的时刻做通知
        notify_stage_director(self.context, entity, ActorLeaveStageEvent(actor_comp.name, helper.current_stage_name, helper.target_stage_name))

        # 离开场景 设置成空
        replace_name = actor_comp.name
        replace_current_stage = "" #设置空！！！！！
        entity.replace(ActorComponent, replace_name, replace_current_stage)
        self.context.change_stage_tag_component(entity, helper.current_stage_name, replace_current_stage)
###############################################################################################################################################
    def after_enter_stage(self, helper: GoToActionHelper) -> None:
        entity: Entity = helper.who
        actor_comp: ActorComponent = entity.get(ActorComponent)
        stagename = actor_comp.current_stage
        actor_entities = self.context.actors_in_stage(stagename)
        for _entity in actor_entities:
            if _entity.has(PerceptionActionComponent):
                continue
            #进入新的场景之后，进入者与场景内所有人都加一次感知，这里会自动检查外观信息
            action = ActorAction(actor_comp.name, PerceptionActionComponent.__name__, [stagename])
            _entity.add(PerceptionActionComponent, action)
###############################################################################################################################################

