from typing import override
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from ecs_systems.components import BroadcastActionComponent, StageComponent
from my_agent.agent_action import AgentAction
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from ecs_systems.stage_director_component import notify_stage_director
from ecs_systems.stage_director_event import IStageDirectorEvent
from builtin_prompt.cn_builtin_prompt import broadcast_action_prompt

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class StageOrActorBroadcastEvent(IStageDirectorEvent):

    def __init__(self, whobroadcast: str, stagename: str, content: str) -> None:
        self.whobroadcast = whobroadcast
        self.stagename = stagename
        self.content = content
    
    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        broadcastcontent = broadcast_action_prompt(self.whobroadcast, self.stagename, self.content)
        return broadcastcontent
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        broadcastcontent = broadcast_action_prompt(self.whobroadcast, self.stagename, self.content)
        return broadcastcontent
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class BroadcastActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(BroadcastActionComponent): GroupEvent.ADDED}
####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(BroadcastActionComponent)
####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.broadcast(entity)  # 核心处理
####################################################################################################
    ## 目前的设定是场景与Actor都能广播，后续会调整与修改。
    def broadcast(self, entity: Entity) -> None:
        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None:
            logger.error(f"BroadcastActionSystem: stageentity is None!")
            return
        #
        broadcastcomp: BroadcastActionComponent = entity.get(BroadcastActionComponent)
        stagecomp: StageComponent = stageentity.get(StageComponent)
        #
        action: AgentAction = broadcastcomp.action
        combine = action.join_values()
        notify_stage_director(self.context, stageentity, StageOrActorBroadcastEvent(action._actor_name, stagecomp.name, combine))
####################################################################################################
