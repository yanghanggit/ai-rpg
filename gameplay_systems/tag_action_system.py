from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import final, override
from components.action_components import TagAction
from game.rpg_entitas_context import RPGEntitasContext
from game.rpg_game import RPGGame


####################################################################################################
@final
class TagActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

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
