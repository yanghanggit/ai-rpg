from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from ecs_systems.action_components import GoToAction, DeadAction, PerceptionAction
from ecs_systems.components import ActorComponent
from my_agent.agent_action import AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from ecs_systems.stage_director_component import (
    StageDirectorComponent,
    OnEnterStageComponent,
)
from typing import cast, override, Optional
from ecs_systems.stage_director_event import IStageDirectorEvent
from ecs_systems.stage_director_system import StageDirectorSystem
import ecs_systems.cn_builtin_prompt as builtin_prompt


###############################################################################################################################################
class GoToActionHelper:

    def __init__(
        self, context: RPGEntitasContext, entity: Entity, target_stage_name: str
    ) -> None:

        self._context: RPGEntitasContext = context
        self._entity: Entity = entity
        self._current_stage_name: str = cast(
            ActorComponent, entity.get(ActorComponent)
        ).current_stage
        self._current_stage_entity: Optional[Entity] = self._context.get_stage_entity(
            self._current_stage_name
        )
        assert self._current_stage_entity is not None
        self._target_stage_name: str = target_stage_name
        self._target_stage_entity: Optional[Entity] = self._context.get_stage_entity(
            target_stage_name
        )
        assert self._target_stage_entity is not None


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class ActorLeaveStageEvent(IStageDirectorEvent):

    def __init__(
        self, actor_name: str, current_stage_name: str, target_stage_name: str
    ) -> None:

        self._actor_name: str = actor_name
        self._current_stage_name: str = current_stage_name
        self._target_stage_name: str = target_stage_name

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        return builtin_prompt.leave_stage_prompt(
            self._actor_name, self._current_stage_name, self._target_stage_name
        )

    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return builtin_prompt.leave_stage_prompt(
            self._actor_name, self._current_stage_name, self._target_stage_name
        )


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class ActorEnterStageEvent(IStageDirectorEvent):

    def __init__(
        self, actor_name: str, target_stage_name: str, last_stage_name: str
    ) -> None:

        self._actor_name: str = actor_name
        self._target_stage_name: str = target_stage_name
        self._last_stage_name: str = last_stage_name

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._actor_name:
            # 目标场景内的一切听到的是这个:"xxx进入了场景"
            return builtin_prompt.enter_stage_prompt1(
                self._actor_name, self._target_stage_name
            )

        # 通知我自己，我从哪里去往了哪里。这样prompt更加清晰一些
        return builtin_prompt.enter_stage_prompt2(
            self._actor_name, self._target_stage_name, self._last_stage_name
        )

    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return builtin_prompt.enter_stage_prompt1(
            self._actor_name, self._target_stage_name
        )


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class GoToActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context

    ###############################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(GoToAction): GroupEvent.ADDED}

    ###############################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GoToAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ###############################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ###############################################################################################################################################
    def handle(self, entity: Entity) -> None:

        assert entity.has(GoToAction)
        go_to_comp = entity.get(GoToAction)
        action: AgentAction = go_to_comp.action
        helper = GoToActionHelper(self._context, entity, action.value(0))
        if (
            helper._target_stage_entity is None
            or helper._current_stage_entity is None
            or helper._target_stage_entity == helper._current_stage_entity
        ):
            return

        if helper._current_stage_entity is not None:
            # 离开前的处理
            self.before_leave_current_stage(helper)
            # 离开
            self.leave_current_stage(helper)

        # 进入新的场景
        self.enter_target_stage(helper)
        # 进入场景后的处理
        self.on_enter_target_stage(helper)

    ###############################################################################################################################################
    def enter_target_stage(self, helper: GoToActionHelper) -> None:

        actor_comp = helper._entity.get(ActorComponent)

        # 真正的进入场景
        helper._entity.replace(
            ActorComponent, actor_comp.name, helper._target_stage_name
        )
        # 添加标记，忽略一次目标场景的导演事件
        helper._entity.replace(OnEnterStageComponent, helper._target_stage_name)
        # 更新场景标记
        self._context.change_stage_tag_component(
            helper._entity, helper._current_stage_name, helper._target_stage_name
        )

        # 进入场景的事件需要通知相关的人
        enter_stage_event = ActorEnterStageEvent(
            actor_comp.name, helper._target_stage_name, helper._current_stage_name
        )
        StageDirectorComponent.add_event_to_stage_director(
            self._context, helper._entity, enter_stage_event
        )

        # 只添加进入场景的事件
        StageDirectorSystem.director_events_to_actor(
            self._context, helper._entity, [enter_stage_event]
        )
        StageDirectorSystem.director_events_to_player(
            self._context, helper._entity, [enter_stage_event]
        )

    ###############################################################################################################################################
    def before_leave_current_stage(self, helper: GoToActionHelper) -> None:
        # 目前就是强行刷一下history
        StageDirectorSystem.director_events_to_actor(
            self._context, helper._entity, None
        )
        StageDirectorSystem.director_events_to_player(
            self._context, helper._entity, None
        )

    ###############################################################################################################################################
    def leave_current_stage(self, helper: GoToActionHelper) -> None:

        actor_comp = helper._entity.get(ActorComponent)

        # 必须在场景信息还有效的时刻做通知
        StageDirectorComponent.add_event_to_stage_director(
            self._context,
            helper._entity,
            ActorLeaveStageEvent(
                actor_comp.name, helper._current_stage_name, helper._target_stage_name
            ),
        )

        # 离开场景 设置成空
        helper._entity.replace(ActorComponent, actor_comp.name, "")

        # 移除这个
        if helper._entity.has(OnEnterStageComponent):
            helper._entity.remove(OnEnterStageComponent)

        # 更新场景标记
        self._context.change_stage_tag_component(
            helper._entity, helper._current_stage_name, ""
        )

    ###############################################################################################################################################
    def on_enter_target_stage(self, helper: GoToActionHelper) -> None:
        actor_comp = helper._entity.get(ActorComponent)
        actor_entities = self._context.actors_in_stage(actor_comp.current_stage)
        for actor_entity in actor_entities:
            if not actor_entity.has(PerceptionAction):
                # 进入新的场景之后，进入者与场景内所有人都加一次感知，这里会自动检查外观信息
                actor_entity.add(
                    PerceptionAction,
                    AgentAction(
                        actor_comp.name,
                        PerceptionAction.__name__,
                        [actor_comp.current_stage],
                    ),
                )


###############################################################################################################################################
