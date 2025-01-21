from typing import final
from entitas import ExecuteProcessor, Matcher  # type: ignore
from overrides import override
from game.rpg_game_context import RPGGameContext
from components.components import (
    PlanningFlagComponent,
)
from game.rpg_game import RPGGame


@final
class PrePlanningSystem(ExecuteProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        entities = self._context.get_group(
            Matcher(PlanningFlagComponent)
        ).entities.copy()
        for entity in entities:
            assert entity.has(PlanningFlagComponent)
            if entity.has(PlanningFlagComponent):
                entity.remove(PlanningFlagComponent)

    ############################################################################################################
