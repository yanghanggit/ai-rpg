from entitas import Entity, Matcher, GroupEvent  # type: ignore
from components.actions import (
    SpeakAction,
)
from typing import final, override
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem


@final
class SpeakActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SpeakAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SpeakAction)

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        pass

    ####################################################################################################################################
