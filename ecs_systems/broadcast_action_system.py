from typing import override
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from ecs_systems.components import StageComponent
from ecs_systems.action_components import BroadcastAction
from my_agent.agent_action import AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from ecs_systems.stage_director_component import StageDirectorComponent
from ecs_systems.stage_director_event import IStageDirectorEvent
from ecs_systems.cn_builtin_prompt import broadcast_action_prompt

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class StageOrActorBroadcastEvent(IStageDirectorEvent):

    def __init__(self, who_broadcast: str, stage_name: str, broadcast_content: str) -> None:
        self._who_broadcast = who_broadcast
        self._stagename = stage_name
        self._broadcast_content = broadcast_content
    
    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        return broadcast_action_prompt(self._who_broadcast, self._stagename, self._broadcast_content)
    
    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return broadcast_action_prompt(self._who_broadcast, self._stagename, self._broadcast_content)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class BroadcastActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context = context
####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(BroadcastAction): GroupEvent.ADDED}
####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(BroadcastAction)
####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.broadcast(entity)  # 核心处理
####################################################################################################
    ## 目前的设定是场景与Actor都能广播，后续会调整与修改。
    def broadcast(self, entity: Entity) -> None:
        current_stage_entity = self._context.safe_get_stage_entity(entity)
        if current_stage_entity is None:
            logger.error(f"BroadcastActionSystem: stageentity is None!")
            return
        #
        broadcast_comp = entity.get(BroadcastAction)
        stage_comp = current_stage_entity.get(StageComponent)
        #
        action: AgentAction = broadcast_comp.action
        join_values = action.join_values()
        StageDirectorComponent.add_event_to_stage_director(self._context, current_stage_entity, StageOrActorBroadcastEvent(action._actor_name, stage_comp.name, join_values))
####################################################################################################
