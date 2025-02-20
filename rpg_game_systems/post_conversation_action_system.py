from typing import final
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from overrides import override
from components.actions import (
    SpeakAction,
    AnnounceAction,
    WhisperAction,
)
from components.components import PlayerActorFlagComponent, ActorComponent
from game.rpg_game_context import RPGGameContext
from game.rpg_game import RPGGame


#################################################################################################################################################
@final
class PostConversationActionSystem(ReactiveProcessor):
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    #################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {
            Matcher(
                any_of=[SpeakAction, AnnounceAction, WhisperAction]
            ): GroupEvent.ADDED
        }

    #################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayerActorFlagComponent) and entity.has(ActorComponent)

    #################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        pass

    #################################################################################################################################################
