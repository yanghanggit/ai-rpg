from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import BroadcastActionComponent, StageComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import IDirectorEvent
from auxiliary.cn_builtin_prompt import broadcast_action_prompt

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class BroadcastEvent(IDirectorEvent):

    def __init__(self, whobroadcast: str, stagename: str, content: str) -> None:
        self.whobroadcast = whobroadcast
        self.stagename = stagename
        self.content = content
    
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        broadcastcontent = broadcast_action_prompt(self.whobroadcast, self.stagename, self.content, extended_context)
        return broadcastcontent
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        broadcastcontent = broadcast_action_prompt(self.whobroadcast, self.stagename, self.content, extended_context)
        return broadcastcontent

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
        #
        action: ActorAction = broadcastcomp.action
        combine = action.single_value()
        notify_stage_director(self.context, stageentity, BroadcastEvent(action.name, stagecomp.name, combine))
