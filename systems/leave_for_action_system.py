from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (
    LeaveForActionComponent, 
    NPCComponent,
    PerceptionActionComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import notify_stage_director
from typing import cast
from auxiliary.director_event import IDirectorEvent
from systems.director_system import director_events_to_npc
from auxiliary.cn_builtin_prompt import ( leave_stage_prompt,
                                          enter_stage_prompt1,
                                          enter_stage_prompt2,
                                          leave_for_stage_failed_because_stage_is_invalid_prompt,
                                          leave_for_stage_failed_because_already_in_stage_prompt)





####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCLeaveForFailedBecauseStageIsInvalidEvent(IDirectorEvent):

    def __init__(self, npcname: str, stagename: str) -> None:
        self.npcname = npcname
        self.stagename = stagename

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npcname:
            # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
            return ""
        leave_for_stage_is_invalid_event = leave_for_stage_failed_because_stage_is_invalid_prompt(self.npcname, self.stagename)
        return leave_for_stage_is_invalid_event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCLeaveForFailedBecauseAlreadyInStage(IDirectorEvent):

    def __init__(self, npcname: str, stagename: str) -> None:
        self.npcname = npcname
        self.stagename = stagename

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npcname:
            # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
            return ""
        already_in_stage_event = leave_for_stage_failed_because_already_in_stage_prompt(self.npcname, self.stagename)
        return already_in_stage_event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""


###############################################################################################################################################
class LeaveActionHelper:

    def __init__(self, context: ExtendedContext, who_wana_leave: Entity, target_stage_name: str) -> None:
        self.context = context
        self.who_wana_leave_entity = who_wana_leave
        self.current_stage_name = cast(NPCComponent, who_wana_leave.get(NPCComponent)).current_stage
        self.current_stage_entity = self.context.getstage(self.current_stage_name)
        self.target_stage_name = target_stage_name
        self.target_stage_entity = self.context.getstage(target_stage_name)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCLeaveStageEvent(IDirectorEvent):

    def __init__(self, npc_name: str, current_stage_name: str, leave_for_stage_name: str) -> None:
        self.npc_name = npc_name
        self.current_stage_name = current_stage_name
        self.leave_for_stage_name = leave_for_stage_name

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        event = leave_stage_prompt(self.npc_name, self.current_stage_name, self.leave_for_stage_name)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = leave_stage_prompt(self.npc_name, self.current_stage_name, self.leave_for_stage_name)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCEnterStageEvent(IDirectorEvent):

    def __init__(self, npc_name: str, stage_name: str, last_stage_name: str) -> None:
        self.npc_name = npc_name
        self.stage_name = stage_name
        self.last_stage_name = last_stage_name

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npc_name:
            # 目标场景内的一切听到的是这个:"xxx进入了场景"
            return enter_stage_prompt1(self.npc_name, self.stage_name)
            
        #通知我自己，我从哪里去往了哪里。这样prompt更加清晰一些
        return enter_stage_prompt2(self.npc_name, self.stage_name, self.last_stage_name)
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = enter_stage_prompt1(self.npc_name, self.stage_name)
        return event    
####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class LeaveForActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(LeaveForActionComponent): GroupEvent.ADDED}

    def filter(self, entity: Entity) -> bool:
        return entity.has(LeaveForActionComponent) and entity.has(NPCComponent)

    def react(self, entities: list[Entity]) -> None:
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
    def enter_stage(self, helper: LeaveActionHelper) -> None:

        entity = helper.who_wana_leave_entity
        current_stage_name = helper.current_stage_name
        target_stage_name = helper.target_stage_name
        target_stage_entity = helper.target_stage_entity
        assert target_stage_entity is not None
        npccomp: NPCComponent = entity.get(NPCComponent)

        replace_name = npccomp.name
        replace_current_stage = target_stage_name
        entity.replace(NPCComponent, replace_name, replace_current_stage)
        self.context.change_stage_tag_component(entity, current_stage_name, replace_current_stage)

        #进入场景的事件需要通知相关的人
        notify_stage_director(self.context, entity, NPCEnterStageEvent(npccomp.name, target_stage_name, current_stage_name))
###############################################################################################################################################
    def before_leave_stage(self, helper: LeaveActionHelper) -> None:
        #目前就是强行刷一下history
        self.direct_before_leave(helper)
###############################################################################################################################################
    def direct_before_leave(self, helper: LeaveActionHelper) -> None:
        director_events_to_npc(self.context, helper.who_wana_leave_entity)
###############################################################################################################################################
    def leave_stage(self, helper: LeaveActionHelper) -> None:
        entity: Entity = helper.who_wana_leave_entity
        npccomp: NPCComponent = entity.get(NPCComponent)
        assert helper.current_stage_entity is not None

        # 必须在场景信息还有效的时刻做通知
        notify_stage_director(self.context, entity, NPCLeaveStageEvent(npccomp.name, helper.current_stage_name, helper.target_stage_name))

        # 离开场景 设置成空
        replace_name = npccomp.name
        replace_current_stage = "" #设置空！！！！！
        entity.replace(NPCComponent, replace_name, replace_current_stage)
        self.context.change_stage_tag_component(entity, helper.current_stage_name, replace_current_stage)
###############################################################################################################################################
    def after_enter_stage(self, helper: LeaveActionHelper) -> None:
        entity: Entity = helper.who_wana_leave_entity
        npccomp: NPCComponent = entity.get(NPCComponent)
        stagename = npccomp.current_stage
        npcs = self.context.npcs_in_this_stage(stagename)
        for npc in npcs:
            if npc.has(PerceptionActionComponent):
                continue
            #进入新的场景之后，进入者与场景内所有人都加一次感知，这里会自动检查外貌信息
            action = ActorAction(npccomp.name, PerceptionActionComponent.__name__, [stagename])
            npc.add(PerceptionActionComponent, action)
###############################################################################################################################################

