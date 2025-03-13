# from components.components import StageComponent
from entitas import Entity, Matcher, GroupEvent  # type: ignore
from components.actions2 import (
    StatusUpdateAction,
)
from typing import final, override
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem


@final
class StatusUpdateActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(StatusUpdateAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(StatusUpdateAction)

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            pass

        # 最后的清理，不要这个了。
        for entity in entities:
            entity.remove(StatusUpdateAction)

    ####################################################################################################################################
