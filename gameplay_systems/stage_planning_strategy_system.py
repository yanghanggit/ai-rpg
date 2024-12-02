from entitas import ExecuteProcessor, Matcher  # type: ignore
from overrides import override
from game.rpg_game_context import RPGGameContext
from components.components import (
    PlanningFlagComponent,
    StageComponent,
)
from game.rpg_game import RPGGame
from typing import final


@final
class StagePlanningStrategySystem(ExecuteProcessor):

    @override
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        stage_entities = self._context.get_group(Matcher(StageComponent)).entities
        for stage_entity in stage_entities:
            stage_comp = stage_entity.get(StageComponent)
            actors_on_stage = self._context._retrieve_actors_on_stage(stage_comp.name)
            if len(actors_on_stage) == 0:
                continue
            stage_entity.replace(PlanningFlagComponent, stage_comp.name)

    ############################################################################################################
