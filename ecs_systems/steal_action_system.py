from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from ecs_systems.action_components import (StealPropActionComponent, CheckStatusActionComponent, DeadActionComponent)
from ecs_systems.components import ActorComponent
from loguru import logger
from my_agent.agent_action import AgentAction
from gameplay_checks.conversation_check import conversation_check, ErrorConversationEnable
from typing import override
from ecs_systems.stage_director_component import notify_stage_director
from ecs_systems.stage_director_event import IStageDirectorEvent
from builtin_prompt.cn_builtin_prompt import steal_prop_action_prompt


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorStealPropEvent(IStageDirectorEvent):

    def __init__(self, who: str, target: str, prop_name: str, action_result: bool) -> None:
        self._who: str = who
        self._target: str = target
        self._prop_name: str = prop_name
        self._action_result: bool = action_result
       
    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self._who or actor_name != self._target:
            return ""
        return steal_prop_action_prompt(self._who, self._target, self._prop_name, self._action_result)
    
    def to_stage(self, stage_name: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class StealActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self._context = context
####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(StealPropActionComponent): GroupEvent.ADDED }
####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(StealPropActionComponent) and entity.has(ActorComponent) and not entity.has(DeadActionComponent)
####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            if self.steal(entity):
                self.on_success(entity)
####################################################################################################################################
    def steal(self, entity: Entity) -> bool:

        steal_success_count = 0
        safename = self._context.safe_get_entity_name(entity)
        logger.debug(f"StealActionSystem: {safename} is stealing")

        steal_comp: StealPropActionComponent = entity.get(StealPropActionComponent)
        steal_action: AgentAction = steal_comp.action
        target_and_message = steal_action.target_and_message_values()
        for tp in target_and_message:
            target = tp[0]
            prop_name = tp[1]
            if conversation_check(self._context, entity, target) != ErrorConversationEnable.VALID:
                # 不能交谈就是不能偷
                continue
            if self._steal(entity, target, prop_name):
                steal_success_count += 1
                notify_stage_director(self._context, entity, ActorStealPropEvent(safename, target, prop_name, True))
            else:
                notify_stage_director(self._context, entity, ActorStealPropEvent(safename, target, prop_name, False))

        return steal_success_count > 0
####################################################################################################################################
    def _steal(self, entity: Entity, target_actor_name: str, prop_name: str) -> bool:
        prop = self._context._file_system.get_prop_file(target_actor_name, prop_name)
        if prop is None:
            return False
        safe_name = self._context.safe_get_entity_name(entity)
        self._context._file_system.give_prop_file(target_actor_name, safe_name, prop_name)
        return True
####################################################################################################################################
    def on_success(self, entity: Entity) -> None:
        if entity.has(CheckStatusActionComponent):
            return
        actor_comp = entity.get(ActorComponent)
        entity.add(CheckStatusActionComponent, AgentAction(actor_comp.name, CheckStatusActionComponent.__name__, [actor_comp.name]))
####################################################################################################################################
