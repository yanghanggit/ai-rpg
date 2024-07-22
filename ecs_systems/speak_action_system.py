from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from ecs_systems.action_components import SpeakActionComponent
from my_agent.agent_action import AgentAction
from my_entitas.extended_context import ExtendedContext
from gameplay_checks.conversation_check import conversation_check, ErrorConversationEnable
from ecs_systems.stage_director_component import notify_stage_director
from ecs_systems.stage_director_event import IStageDirectorEvent
from typing import override
from builtin_prompt.cn_builtin_prompt import speak_action_prompt



####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class StageOrActorSpeakEvent(IStageDirectorEvent):

    def __init__(self, who: str, target: str, message: str) -> None:
        self._who: str = who
        self._target: str = target
        self._message: str = message

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        return speak_action_prompt(self._who, self._target, self._message)
    
    def to_stage(self, stage_name: str, extended_context: ExtendedContext) -> str:
        return speak_action_prompt(self._who, self._target, self._message)
####################################################################################################################################
class SpeakActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self._context = context
####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SpeakActionComponent): GroupEvent.ADDED}
####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SpeakActionComponent)
####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.speak(entity)  
####################################################################################################################################
    def speak(self, entity: Entity) -> None:
        speak_comp = entity.get(SpeakActionComponent)
        speak_action: AgentAction = speak_comp.action
        safe_name = self._context.safe_get_entity_name(entity)
        target_and_message = speak_action.target_and_message_values()
        for tp in target_and_message:
            target = tp[0]
            message = tp[1]
            if conversation_check(self._context, entity, target) != ErrorConversationEnable.VALID:
                continue
            notify_stage_director(self._context, entity, StageOrActorSpeakEvent(safe_name, target, message))
####################################################################################################################################
