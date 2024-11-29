from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import final, override
from components.action_components import StageNarrateAction
from game.rpg_entitas_context import RPGEntitasContext
from game.rpg_game import RPGGame


@final
class StageNarrateActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(StageNarrateAction): GroupEvent.ADDED}

    ############################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(StageNarrateAction)

    ############################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        pass

    ############################################################################################################
