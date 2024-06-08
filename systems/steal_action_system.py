from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (  StealActionComponent, CheckStatusActionComponent, DeadActionComponent,
                                    ActorComponent)
from loguru import logger
from auxiliary.actor_plan_and_action import ActorAction
from auxiliary.target_and_message_format_handle import conversation_check, parse_target_and_message, ErrorConversationEnable
from typing import Optional, override
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import IDirectorEvent
from auxiliary.cn_builtin_prompt import steal_action_prompt


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorStealEvent(IDirectorEvent):

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

        steal_any_success = False
        safename = self.context.safe_get_entity_name(entity)
        logger.debug(f"StealActionSystem: {safename} is stealing")

        stealcomp: StealActionComponent = entity.get(StealActionComponent)
        stealaction: ActorAction = stealcomp.action
        for value in stealaction.values:

            parse = parse_target_and_message(value)
            targetname: Optional[str] = parse[0]
            message: Optional[str] = parse[1]
            
            if targetname is None or message is None:
                # 不能交谈就是不能偷
                continue
    
            if conversation_check(self.context, entity, targetname) != ErrorConversationEnable.VALID:
                # 不能交谈就是不能偷
                continue
        
            propname = message
            stealres = self._steal_(entity, targetname, propname)
            notify_stage_director(self.context, entity, ActorStealEvent(safename, targetname, propname, stealres))
            if stealres:
                steal_any_success = True

        return steal_any_success
###################################################################################################################
    def _steal_(self, entity: Entity, target_actor_name: str, propname: str) -> bool:
        filesystem = self.context.file_system
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
        action = ActorAction(actor_comp.name, CheckStatusActionComponent.__name__, [actor_comp.name])
        entity.add(CheckStatusActionComponent, action)
#####################################################################################################################
