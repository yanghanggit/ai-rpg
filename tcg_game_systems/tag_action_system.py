from entitas import Entity, Matcher, GroupEvent  # type: ignore
from typing import final, override, cast
from components.actions import TagAction
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem


####################################################################################################
@final
class TagActionSystem(BaseActionReactiveSystem):

    ####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(TagAction): GroupEvent.ADDED}

    ####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(TagAction)

    ####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        pass


####################################################################################################
