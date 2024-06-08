from typing import override
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (GoToActionComponent, PortalStepActionComponent, DeadActionComponent,
                        ActorComponent, 
                        ExitOfPortalComponent,)
from auxiliary.actor_plan_and_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger

###############################################################################################################################################
class PortalStepActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
###############################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PortalStepActionComponent): GroupEvent.ADDED}
###############################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        # 只有NPC才能触发这个系统
        return entity.has(PortalStepActionComponent) and entity.has(ActorComponent) and not entity.has(DeadActionComponent)
###############################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
         for entity in entities:
            self.portalstep(entity)
###############################################################################################################################################
    def portalstep(self, entity: Entity) -> None:
        
        npccomp: ActorComponent = entity.get(ActorComponent)
        portalstepcomp: PortalStepActionComponent = entity.get(PortalStepActionComponent)
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

        # 取出当前场景
        stageentity = self.context.get_stage_entity(stagename)
        assert stageentity is not None, f"PortalStepActionSystem: {stagename} is None"
        if not stageentity.has(ExitOfPortalComponent):
            # 该场景没有连接到任何场景，所以不能"盲目"的离开
            logger.error(f"PortalStepActionSystem: {npccomp.name} 想要离开的场景是: {stagename}, 该场景没有连接到任何场景")
            return
        
        # 取出数据，并准备沿用GoToActionComponent
        exit_of_portal_comp: ExitOfPortalComponent = stageentity.get(ExitOfPortalComponent)
        logger.debug(f"PortalStepActionSystem: {npccomp.name} 想要离开的场景是: {stagename}, 该场景可以连接的场景有: {exit_of_portal_comp.name}")
        target_stage_entity = self.context.get_stage_entity(exit_of_portal_comp.name)
        if target_stage_entity is None:
            logger.error(f"PortalStepActionSystem: {npccomp.name} 想要离开的场景是: {stagename}, 该场景可以连接的场景有: {exit_of_portal_comp.name}, 但是该场景不存在")
            return
        
        logger.debug(f"{exit_of_portal_comp.name}允许{npccomp.name}前往")
        
        # 生成离开当前场景的动作
        action = ActorAction(npccomp.name, GoToActionComponent.__name__, [exit_of_portal_comp.name])
        entity.add(GoToActionComponent, action)
###############################################################################################################################################       

            
