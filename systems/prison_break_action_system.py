from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (LeaveForActionComponent, PrisonBreakActionComponent,
                        NPCComponent, 
                        ConnectToStageComponent,)
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger

###############################################################################################################################################
class PrisonBreakActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
###############################################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PrisonBreakActionComponent): GroupEvent.ADDED}
###############################################################################################################################################
    def filter(self, entity: Entity) -> bool:
        # 只有NPC才能触发这个系统
        return entity.has(PrisonBreakActionComponent) and entity.has(NPCComponent)
###############################################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  PrisonBreakActionSystem  >>>>>>>>>>>>>>>>>")
        self.prisonbreak(entities)
###############################################################################################################################################
    def prisonbreak(self, entities: list[Entity]) -> None:
        for npcentity in entities:
            npccomp: NPCComponent = npcentity.get(NPCComponent)
            prisonbreakcomp: PrisonBreakActionComponent = npcentity.get(PrisonBreakActionComponent)
            action: ActorAction = prisonbreakcomp.action
            if len(action.values) == 0:
               logger.error(f"PrisonBreakActionSystem: {action} has no action values")
               continue
            
            #
            logger.debug(f"PrisonBreakActionSystem: {action}")
            stagename = action.values[0]
            logger.debug(f"PrisonBreakActionSystem: {npccomp.name} 想要去往的场景是: {stagename}")
            if stagename != npccomp.current_stage:
                # 只能脱离当前场景
                logger.error(f"PrisonBreakActionSystem: {npccomp.name} 只能脱离当前场景 {npccomp.current_stage}, 但是action里的场景对不上 {stagename}")
                continue

            # 取出当前场景！
            stageentity = self.context.getstage(stagename)
            assert stageentity is not None, f"PrisonBreakActionSystem: {stagename} is None"
            if not stageentity.has(ConnectToStageComponent):
                # 该场景没有连接到任何场景，所以不能"盲目"的离开
                logger.error(f"PrisonBreakActionSystem: {npccomp.name} 想要去往的场景是: {stagename}, 该场景没有连接到任何场景")
                continue
            
            # 取出数据，并准备沿用LeaveForActionComponent
            conncectstagecomp: ConnectToStageComponent = stageentity.get(ConnectToStageComponent)
            logger.debug(f"PrisonBreakActionSystem: {npccomp.name} 想要去往的场景是: {stagename}, 该场景可以连接的场景有: {conncectstagecomp.name}")
            connect_stage_entity = self.context.getstage(conncectstagecomp.name)
            if connect_stage_entity is None:
                logger.error(f"PrisonBreakActionSystem: {npccomp.name} 想要去往的场景是: {stagename}, 该场景可以连接的场景有: {conncectstagecomp.name}, 但是该场景不存在")
                continue

            # 生成离开当前场景的动作
            action = ActorAction(npccomp.name, LeaveForActionComponent.__name__, [conncectstagecomp.name])
            npcentity.add(LeaveForActionComponent, action)
###############################################################################################################################################       

            
