from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from ecs_systems.action_components import WhisperActionComponent
from my_agent.agent_action import AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override
from gameplay_checks.conversation_check import conversation_check, ErrorConversationEnable
from ecs_systems.stage_director_component import StageDirectorComponent
from ecs_systems.stage_director_event import IStageDirectorEvent
from ecs_systems.cn_builtin_prompt import whisper_action_prompt


####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class StageOrActorWhisperEvent(IStageDirectorEvent):
    
    def __init__(self, who: str, target: str, message: str) -> None:
        self._who: str = who
        self._target: str = target
        self._message: str = message

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._who or actor_name != self._target:
            # 只有这2个人才能听到
            return ""
        return whisper_action_prompt(self._who, self._target, self._message)
    
    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        ## 场景应该是彻底听不到
        return ""
####################################################################################################################################
class WhisperActionSystem(ReactiveProcessor):
    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context = context
####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(WhisperActionComponent): GroupEvent.ADDED}
####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(WhisperActionComponent)
####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.whisper(entity) 
####################################################################################################################################
    def whisper(self, entity: Entity) -> None:
        whisper_comp: WhisperActionComponent = entity.get(WhisperActionComponent)
        action: AgentAction = whisper_comp.action
        safe_name = self._context.safe_get_entity_name(entity)
        target_and_message = action.target_and_message_values()
        for tp in target_and_message:
            targetname = tp[0]
            message = tp[1]
            if conversation_check(self._context, entity, targetname) != ErrorConversationEnable.VALID:
                continue
            StageDirectorComponent.add_event_to_stage_director(self._context, entity, StageOrActorWhisperEvent(safe_name, targetname, message))
####################################################################################################################################
