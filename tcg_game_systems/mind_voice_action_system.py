from entitas import Entity, Matcher, GroupEvent  # type: ignore
from components.actions2 import (
    MindVoiceAction2,
)
from typing import final, override
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from loguru import logger
from components.components import ActorComponent


####################################################################################################################################
@final
class MindVoiceActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(MindVoiceAction2): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(MindVoiceAction2) and entity.has(ActorComponent)

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_mindvoice_action(entity)

    ####################################################################################################################################
    def _process_mindvoice_action(self, entity: Entity) -> None:
        mind_voice_action = entity.get(MindVoiceAction2)
        assert mind_voice_action is not None
        logger.info(
            f"MindVoiceActionSystem:\n{mind_voice_action.name}:\n{mind_voice_action.data}"
        )

    ####################################################################################################################################
