from entitas import Entity, Matcher, GroupEvent  # type: ignore
from models.actions_v_0_0_1 import (
    MindVoiceAction,
)
from typing import final, override
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from models.components_v_0_0_1 import ActorComponent
from models.agent_event_v_0_0_1 import MindVoiceEvent

# from loguru import logger


####################################################################################################################################
@final
class MindVoiceActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(MindVoiceAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(MindVoiceAction) and entity.has(ActorComponent)

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    ####################################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        mind_voice_action = entity.get(MindVoiceAction)
        assert mind_voice_action is not None
        self._game.notify_event(
            set({entity}),
            MindVoiceEvent(
                message=f"{mind_voice_action.name}:{mind_voice_action.data}",
                speaker=mind_voice_action.name,
                dialogue=mind_voice_action.data,
            ),
        )

    ####################################################################################################################################
