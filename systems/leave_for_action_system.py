from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (LeaveForActionComponent, 
                        NPCComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import DirectorComponent
from auxiliary.director_event import NPCLeaveForStageEvent, NPCEnterStageEvent
from typing import cast


###############################################################################################################################################
class LeaveActionHelper:

    def __init__(self, context: ExtendedContext, who_wana_leave: Entity, target_stage_name: str) -> None:
        self.context = context
        self.who_wana_leave = who_wana_leave
        self.current_stage_name = cast(NPCComponent, who_wana_leave.get(NPCComponent)).current_stage
        self.currentstage = self.context.getstage(self.current_stage_name)
        self.target_stage_name = target_stage_name
        self.target_stage = self.context.getstage(target_stage_name)

###############################################################################################################################################
class LeaveForActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(LeaveForActionComponent): GroupEvent.ADDED}

    def filter(self, entity: Entity) -> bool:
        return entity.has(LeaveForActionComponent) and entity.has(NPCComponent)

    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  LeaveForActionSystem  >>>>>>>>>>>>>>>>>")
        self.leavefor(entities)

    ###############################################################################################################################################
    def leavefor(self, entities: list[Entity]) -> None:

        for entity in entities:
            if not entity.has(NPCComponent):
                logger.warning(f"LeaveForActionSystem: {entity} is not NPC?!")
                continue
            
            leavecomp: LeaveForActionComponent = entity.get(LeaveForActionComponent)
            action: ActorAction = leavecomp.action
            if len(action.values) == 0:
               continue
   
            stagename = action.values[0]
            handle = LeaveActionHelper(self.context, entity, stagename)
            if handle.target_stage is None or handle.currentstage is None or handle.target_stage == handle.currentstage:
                continue

            if handle.currentstage is not None:
                self.leave_stage(handle)
           
            self.enter_stage(handle)
    ###############################################################################################################################################            
    def enter_stage(self, handle: LeaveActionHelper) -> None:
        entity = handle.who_wana_leave
        current_stage_name = handle.current_stage_name
        target_stage_name = handle.target_stage_name
        target_stage_entity = handle.target_stage
        assert target_stage_entity is not None
        npccomp: NPCComponent = entity.get(NPCComponent)

        replace_name = npccomp.name
        replace_current_stage = target_stage_name
        entity.replace(NPCComponent, replace_name, replace_current_stage)
        self.context.change_stage_tag_component(entity, current_stage_name, replace_current_stage)

        # if current_stage_name != "":
        #     self.notify_director_leave_for_stage(target_stage_entity, npccomp.name, current_stage_name, target_stage_name)
        # else:
        #     self.notify_director_enter_stage(target_stage_entity, npccomp.name, target_stage_name)
        self.notify_director_enter_stage(target_stage_entity, npccomp.name, target_stage_name)
    ###############################################################################################################################################
    def leave_stage(self, handle: LeaveActionHelper) -> None:
        entity: Entity = handle.who_wana_leave
        npccomp: NPCComponent = entity.get(NPCComponent)
        assert handle.currentstage is not None
        currentstage: Entity = handle.currentstage

        replace_name = npccomp.name
        replace_current_stage = "" #设置空！！！！！
        entity.replace(NPCComponent, replace_name, replace_current_stage)
        
        self.context.change_stage_tag_component(entity, handle.current_stage_name, replace_current_stage)
        self.notify_director_leave_for_stage(currentstage, npccomp.name, handle.current_stage_name, handle.target_stage_name)
    ###############################################################################################################################################
    def notify_director_leave_for_stage(self, stageentity: Entity, npcname: str, cur_stage_name: str, target_stage_name: str) -> None:
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        leaveforstageevent = NPCLeaveForStageEvent(npcname, cur_stage_name, target_stage_name)
        directorcomp.addevent(leaveforstageevent)
    ###############################################################################################################################################
    def notify_director_enter_stage(self, stageentity: Entity, npcname: str, target_stage_name: str) -> None:
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        enterstageevent = NPCEnterStageEvent(npcname, target_stage_name)
        directorcomp.addevent(enterstageevent)
    ###############################################################################################################################################
    
