from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from ecs_systems.components import (
    GoToActionComponent, 
    ActorComponent,
    DeadActionComponent,
    PerceptionActionComponent)
from my_agent.agent_action import AgentAction
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from ecs_systems.stage_director_component import notify_stage_director
from typing import cast, override, List, Optional
from ecs_systems.stage_director_event import IStageDirectorEvent
from ecs_systems.stage_director_system import director_events_to_actor
from builtin_prompt.cn_builtin_prompt import ( leave_stage_prompt,
                                          enter_stage_prompt1,
                                          enter_stage_prompt2)

###############################################################################################################################################
class GoToActionHelper:

    def __init__(self, context: ExtendedContext, who: Entity, target_stage_name: str) -> None:

        self._context: ExtendedContext = context
        self._who: Entity = who
        self._current_stage_name: str = cast(ActorComponent, who.get(ActorComponent)).current_stage
        self._current_stage_entity: Optional[Entity]  = self._context.get_stage_entity(self._current_stage_name)
        assert self._current_stage_entity is not None
        self._target_stage_name: str = target_stage_name
        self._target_stage_entity: Optional[Entity] = self._context.get_stage_entity(target_stage_name)
        assert self._target_stage_entity is not None
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class ActorLeaveStageEvent(IStageDirectorEvent):

    def __init__(self, actor_name: str, current_stage_name: str, goto_stage_name: str) -> None:

        self._actor_name: str = actor_name
        self._current_stage_name: str = current_stage_name
        self._goto_stage_name: str = goto_stage_name

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        return leave_stage_prompt(self._actor_name, self._current_stage_name, self._goto_stage_name)
    
    def to_stage(self, stage_name: str, extended_context: ExtendedContext) -> str:
        return leave_stage_prompt(self._actor_name, self._current_stage_name, self._goto_stage_name)
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class ActorEnterStageEvent(IStageDirectorEvent):

    def __init__(self, actor_name: str, stage_name: str, last_stage_name: str) -> None:

        self._actor_name: str = actor_name
        self._stage_name: str = stage_name
        self._last_stage_name: str = last_stage_name

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self._actor_name:
            # 目标场景内的一切听到的是这个:"xxx进入了场景"
            return enter_stage_prompt1(self._actor_name, self._stage_name)
            
        #通知我自己，我从哪里去往了哪里。这样prompt更加清晰一些
        return enter_stage_prompt2(self._actor_name, self._stage_name, self._last_stage_name)
    
    def to_stage(self, stage_name: str, extended_context: ExtendedContext) -> str:
        return enter_stage_prompt1(self._actor_name, self._stage_name)    
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class GoToActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self._context = context
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
            
            go_to_action_comp = entity.get(GoToActionComponent)
            action: AgentAction = go_to_action_comp.action
            # if len(action._values) == 0:
            #    continue
            stage_name = action.value(0)
            if stage_name == "":
                logger.error(f"GoToActionSystem: {action} has no stage name")
                continue

            handle = GoToActionHelper(self._context, entity, stage_name)
            if handle._target_stage_entity is None or handle._current_stage_entity is None or handle._target_stage_entity == handle._current_stage_entity:
                continue

            if handle._current_stage_entity is not None:
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

        entity = helper._who
        current_stage_name = helper._current_stage_name
        target_stage_name = helper._target_stage_name
        target_stage_entity = helper._target_stage_entity
        assert target_stage_entity is not None
        actor_comp: ActorComponent = entity.get(ActorComponent)

        replace_name = actor_comp.name
        replace_current_stage = target_stage_name
        entity.replace(ActorComponent, replace_name, replace_current_stage)
        self._context.change_stage_tag_component(entity, current_stage_name, replace_current_stage)

        #进入场景的事件需要通知相关的人
        notify_stage_director(self._context, entity, ActorEnterStageEvent(actor_comp.name, target_stage_name, current_stage_name))
###############################################################################################################################################
    def before_leave_stage(self, helper: GoToActionHelper) -> None:
        #目前就是强行刷一下history
        self.direct_before_leave(helper)
###############################################################################################################################################
    def direct_before_leave(self, helper: GoToActionHelper) -> None:
        director_events_to_actor(self._context, helper._who)
###############################################################################################################################################
    def leave_stage(self, helper: GoToActionHelper) -> None:
        entity: Entity = helper._who
        actor_comp: ActorComponent = entity.get(ActorComponent)
        assert helper._current_stage_entity is not None

        # 必须在场景信息还有效的时刻做通知
        notify_stage_director(self._context, entity, ActorLeaveStageEvent(actor_comp.name, helper._current_stage_name, helper._target_stage_name))

        # 离开场景 设置成空
        replace_name = actor_comp.name
        replace_current_stage = "" #设置空！！！！！
        entity.replace(ActorComponent, replace_name, replace_current_stage)
        self._context.change_stage_tag_component(entity, helper._current_stage_name, replace_current_stage)
###############################################################################################################################################
    def after_enter_stage(self, helper: GoToActionHelper) -> None:
        entity: Entity = helper._who
        actor_comp: ActorComponent = entity.get(ActorComponent)
        stagename = actor_comp.current_stage
        actor_entities = self._context.actors_in_stage(stagename)
        for _entity in actor_entities:
            if _entity.has(PerceptionActionComponent):
                continue
            #进入新的场景之后，进入者与场景内所有人都加一次感知，这里会自动检查外观信息
            action = AgentAction(actor_comp.name, PerceptionActionComponent.__name__, [stagename])
            _entity.add(PerceptionActionComponent, action)
###############################################################################################################################################

