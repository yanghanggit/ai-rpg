from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from ecs_systems.action_components import WhisperAction
from my_agent.agent_action import AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override
import gameplay.conversation_helper
from ecs_systems.stage_director_component import StageDirectorComponent
from ecs_systems.stage_director_event import IStageDirectorEvent
import ecs_systems.cn_builtin_prompt as builtin_prompt


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
        return builtin_prompt.whisper_action_prompt(
            self._who, self._target, self._message
        )

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
        return {Matcher(WhisperAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(WhisperAction)

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.whisper(entity)

    ####################################################################################################################################
    def whisper(self, entity: Entity) -> None:
        whisper_comp: WhisperAction = entity.get(WhisperAction)
        action: AgentAction = whisper_comp.action
        safe_name = self._context.safe_get_entity_name(entity)
        target_and_message = action.target_and_message_values()
        for tp in target_and_message:
            targetname = tp[0]
            message = tp[1]
            if (
                gameplay.conversation_helper.check_conversation_enable(
                    self._context, entity, targetname
                )
                != gameplay.conversation_helper.ErrorConversationEnable.VALID
            ):
                continue
            StageDirectorComponent.add_event_to_stage_director(
                self._context,
                entity,
                StageOrActorWhisperEvent(safe_name, targetname, message),
            )


####################################################################################################################################
