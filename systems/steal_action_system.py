from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (  StealActionComponent,
                                    NPCComponent)
from loguru import logger
from auxiliary.actor_action import ActorAction
from auxiliary.dialogue_rule import dialogue_enable, parse_target_and_message, ErrorDialogueEnable
from typing import Optional
from auxiliary.director_component import DirectorComponent
from auxiliary.director_event import NPCStealEvent


class StealActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(StealActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(StealActionComponent) and entity.has(NPCComponent)
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  StealActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.steal(entity)
###################################################################################################################
    def steal(self, entity: Entity) -> None:
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
    
            if dialogue_enable(self.context, entity, targetname) != ErrorDialogueEnable.VALID:
                # 不能交谈就是不能偷
                continue
        
            propname = message
            stealres = self._steal_(entity, targetname, propname)
            self.notifydirector(entity, targetname, propname, stealres)
###################################################################################################################
    def _steal_(self, entity: Entity, target_npc_name: str, propname: str) -> bool:
        filesystem = self.context.file_system
        prop = filesystem.get_prop_file(target_npc_name, propname)
        if prop is None:
            return False
        safename = self.context.safe_get_entity_name(entity)
        filesystem.exchange_prop_file(target_npc_name, safename, propname)
        return True
####################################################################################################
    def notifydirector(self, entity: Entity, targetname: str, steal_prop_name: str, success: bool) -> None:
        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        safename = self.context.safe_get_entity_name(entity)
        if safename == "":
            return
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        directorcomp.addevent(NPCStealEvent(safename, targetname, steal_prop_name, success))
###################################################################################################################