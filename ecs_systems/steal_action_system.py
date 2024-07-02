from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from ecs_systems.components import (  StealActionComponent, CheckStatusActionComponent, DeadActionComponent,
                                    ActorComponent)
from loguru import logger
from my_agent.agent_action import AgentAction
from gameplay_checks.conversation_check import conversation_check, ErrorConversationEnable
from typing import Optional, override
from ecs_systems.stage_director_component import notify_stage_director
from ecs_systems.stage_director_event import IStageDirectorEvent
from builtin_prompt.cn_builtin_prompt import steal_action_prompt


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorStealEvent(IStageDirectorEvent):

    def __init__(self, whosteal: str, targetname: str, propname: str, stealres: bool) -> None:
        self.whosteal = whosteal
        self.targetname = targetname
        self.propname = propname
        self.stealres = stealres
       
    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self.whosteal or actor_name != self.targetname:
            return ""
        
        stealcontent = steal_action_prompt(self.whosteal, self.targetname, self.propname, self.stealres)
        return stealcontent
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""

class StealActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(StealActionComponent): GroupEvent.ADDED }
###################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(StealActionComponent) and entity.has(ActorComponent) and not entity.has(DeadActionComponent)
###################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            steal_any = self.steal(entity)
            if steal_any:
                self.after_steal_success(entity)
###################################################################################################################
    def steal(self, entity: Entity) -> bool:

        steal_any = False
        safename = self.context.safe_get_entity_name(entity)
        logger.debug(f"StealActionSystem: {safename} is stealing")

        steal_comp: StealActionComponent = entity.get(StealActionComponent)
        steal_action: AgentAction = steal_comp.action
        target_and_message = steal_action.target_and_message_values()
        for tp in target_and_message:
            target = tp[0]
            message = tp[1]
            if conversation_check(self.context, entity, target) != ErrorConversationEnable.VALID:
                # 不能交谈就是不能偷
                continue
        
            propname = message
            steal_res = self._steal_(entity, target, propname)
            notify_stage_director(self.context, entity, ActorStealEvent(safename, target, propname, steal_res))
            if steal_res:
                steal_any = True

        return steal_any
###################################################################################################################
    def _steal_(self, entity: Entity, target_actor_name: str, propname: str) -> bool:
        filesystem = self.context._file_system
        prop = filesystem.get_prop_file(target_actor_name, propname)
        if prop is None:
            return False
        safename = self.context.safe_get_entity_name(entity)
        filesystem.exchange_prop_file(target_actor_name, safename, propname)
        return True
###################################################################################################################
    def after_steal_success(self, entity: Entity) -> None:
        if entity.has(CheckStatusActionComponent):
            return
        actor_comp: ActorComponent = entity.get(ActorComponent)
        action = AgentAction(actor_comp.name, CheckStatusActionComponent.__name__, [actor_comp.name])
        entity.add(CheckStatusActionComponent, action)
#####################################################################################################################
