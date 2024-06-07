from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (LeaveForActionComponent, PortalStepActionComponent, DeadActionComponent,
                        NPCComponent, 
                        ExitOfPortalComponent,)
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
# from auxiliary.director_event import IDirectorEvent
# from auxiliary.director_component import notify_stage_director
# from auxiliary.cn_builtin_prompt import portal_break_action_begin_prompt

# class NPCPortalStepBeginEvent(IDirectorEvent):

#     def __init__(self, who_is_planning_portal_break: str, stagename: str) -> None:
#         self.who_is_planning_portal_break = who_is_planning_portal_break
#         self.stagename = stagename
    
#     def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
#         return portal_break_action_begin_prompt(self.who_is_planning_portal_break, self.stagename, extended_context)
    
#     def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
#         return portal_break_action_begin_prompt(self.who_is_planning_portal_break, self.stagename, extended_context)


#可以改成这个名字：PortalStepAction
###############################################################################################################################################
class PortalStepActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
###############################################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PortalStepActionComponent): GroupEvent.ADDED}
###############################################################################################################################################
    def filter(self, entity: Entity) -> bool:
        # 只有NPC才能触发这个系统
        return entity.has(PortalStepActionComponent) and entity.has(NPCComponent) and not entity.has(DeadActionComponent)
###############################################################################################################################################
    def react(self, entities: list[Entity]) -> None:
         for npcentity in entities:
            self.portalstep(npcentity)
###############################################################################################################################################
    def portalstep(self, npcentity: Entity) -> None:
        
        npccomp: NPCComponent = npcentity.get(NPCComponent)
        portalstepcomp: PortalStepActionComponent = npcentity.get(PortalStepActionComponent)
        action: ActorAction = portalstepcomp.action
        if len(action.values) == 0:
            logger.error(f"PortalStepActionSystem: {action} has no action values")
            return
        #
        # logger.debug(f"PortalStepActionSystem: {action}")
        stagename = action.values[0]
        logger.debug(f"PortalStepActionSystem: {npccomp.name} 想要离开的场景是: {stagename}")
        if stagename != npccomp.current_stage:
            # 只能脱离当前场景
            logger.error(f"PortalStepActionSystem: {npccomp.name} 只能脱离当前场景 {npccomp.current_stage}, 但是action里的场景对不上 {stagename}")
            return

        # 取出当前场景！
        stageentity = self.context.getstage(stagename)
        assert stageentity is not None, f"PortalStepActionSystem: {stagename} is None"
        if not stageentity.has(ExitOfPortalComponent):
            # 该场景没有连接到任何场景，所以不能"盲目"的离开
            logger.error(f"PortalStepActionSystem: {npccomp.name} 想要离开的场景是: {stagename}, 该场景没有连接到任何场景")
            return
        
        # 取出数据，并准备沿用LeaveForActionComponent
        conncectstagecomp: ExitOfPortalComponent = stageentity.get(ExitOfPortalComponent)
        logger.debug(f"PortalStepActionSystem: {npccomp.name} 想要离开的场景是: {stagename}, 该场景可以连接的场景有: {conncectstagecomp.name}")
        connect_stage_entity = self.context.getstage(conncectstagecomp.name)
        if connect_stage_entity is None:
            logger.error(f"PortalStepActionSystem: {npccomp.name} 想要离开的场景是: {stagename}, 该场景可以连接的场景有: {conncectstagecomp.name}, 但是该场景不存在")
            return
        
        logger.debug(f"{conncectstagecomp.name}允许{npccomp.name}前往")
        
        # 这里先提示，如果后续因为场景条件而被打断，到时候再提示
        #notify_stage_director(self.context, stageentity, NPCPortalStepBeginEvent(npccomp.name, stagename))

        # 生成离开当前场景的动作
        action = ActorAction(npccomp.name, LeaveForActionComponent.__name__, [conncectstagecomp.name])
        npcentity.add(LeaveForActionComponent, action)
###############################################################################################################################################       

            
