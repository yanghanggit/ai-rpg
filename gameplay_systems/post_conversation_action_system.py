from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from overrides import override
from gameplay_systems.action_components import (
    SpeakAction,
    BroadcastAction,
    WhisperAction,
)
from gameplay_systems.components import PlayerComponent, ActorComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext


#################################################################################################################################################
class PostConversationActionSystem(ReactiveProcessor):
    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)

    #################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {
            Matcher(
                any_of=[SpeakAction, BroadcastAction, WhisperAction]
            ): GroupEvent.ADDED
        }

    #################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayerComponent) and entity.has(ActorComponent)

    #################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        pass

    #################################################################################################################################################
