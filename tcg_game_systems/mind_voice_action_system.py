from entitas import Entity, Matcher, GroupEvent  # type: ignore
from components.actions import (
    MindVoiceAction,
)

from typing import final, override
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem


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
        return entity.has(MindVoiceAction)

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        pass
