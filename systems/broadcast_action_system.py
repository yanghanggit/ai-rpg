
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import BroadcastActionComponent, StageComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import DirectorComponent
from auxiliary.director_event import BroadcastEvent

class BroadcastActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(BroadcastActionComponent): GroupEvent.ADDED}
####################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(BroadcastActionComponent)
####################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  BroadcastActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.broadcast(entity)  # 核心处理
####################################################################################################
    ## 目前的设定是场景与NPC都能广播，后续会调整与修改。
    def broadcast(self, entity: Entity) -> None:
        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None:
            logger.error(f"BroadcastActionSystem: stageentity is None!")
            return
        #
        broadcastcomp: BroadcastActionComponent = entity.get(BroadcastActionComponent)
        stagecomp: StageComponent = stageentity.get(StageComponent)
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        #
        action: ActorAction = broadcastcomp.action
        for value in action.values:
            event = BroadcastEvent(action.name, stagecomp.name, value)
            directorcomp.addevent(event)
####################################################################################################          
        
                