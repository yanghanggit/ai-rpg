from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from ecs_systems.action_components import (StealActionComponent, CheckStatusActionComponent, DeadActionComponent)
from ecs_systems.components import ActorComponent
from loguru import logger
from my_agent.agent_action import AgentAction
from gameplay_checks.conversation_check import conversation_check, ErrorConversationEnable
from typing import override
from ecs_systems.stage_director_component import notify_stage_director
from ecs_systems.stage_director_event import IStageDirectorEvent
from builtin_prompt.cn_builtin_prompt import steal_action_prompt


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorStealEvent(IStageDirectorEvent):

    def __init__(self, who: str, target: str, prop_name: str, steal_result: bool) -> None:
        self._who: str = who
        self._target: str = target
        self._prop_name: str = prop_name
        self._steal_result: bool = steal_result
       
    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self._who or actor_name != self._target:
            return ""
        return steal_action_prompt(self._who, self._target, self._prop_name, self._steal_result)
    
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
        return { Matcher(StealActionComponent): GroupEvent.ADDED }
####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(StealActionComponent) and entity.has(ActorComponent) and not entity.has(DeadActionComponent)
####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            steal_any = self.steal(entity)
            if steal_any:
                self.after_steal_success(entity)
####################################################################################################################################
    def steal(self, entity: Entity) -> bool:

        steal_any = False
        safename = self._context.safe_get_entity_name(entity)
        logger.debug(f"StealActionSystem: {safename} is stealing")

        steal_comp: StealActionComponent = entity.get(StealActionComponent)
        steal_action: AgentAction = steal_comp.action
        target_and_message = steal_action.target_and_message_values()
        for tp in target_and_message:
            target = tp[0]
            message = tp[1]
            if conversation_check(self._context, entity, target) != ErrorConversationEnable.VALID:
                # 不能交谈就是不能偷
                continue
        
            propname = message
            steal_res = self._steal_(entity, target, propname)
            notify_stage_director(self._context, entity, ActorStealEvent(safename, target, propname, steal_res))
            if steal_res:
                steal_any = True

        return steal_any
####################################################################################################################################
    def _steal_(self, entity: Entity, target_actor_name: str, propname: str) -> bool:
        prop = self._context._file_system.get_prop_file(target_actor_name, propname)
        if prop is None:
            return False
        safename = self._context.safe_get_entity_name(entity)
        self._context._file_system.exchange_prop_file(target_actor_name, safename, propname)
        return True
####################################################################################################################################
    def after_steal_success(self, entity: Entity) -> None:
        if entity.has(CheckStatusActionComponent):
            return
        actor_comp = entity.get(ActorComponent)
        entity.add(CheckStatusActionComponent, AgentAction(actor_comp.name, CheckStatusActionComponent.__name__, [actor_comp.name]))
####################################################################################################################################
