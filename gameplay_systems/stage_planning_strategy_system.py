from entitas import ExecuteProcessor, Matcher  # type: ignore
from overrides import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_components.components import (
    PlanningAllowedComponent,
    StageComponent,
)
from rpg_game.rpg_game import RPGGame
from typing import final


@final
class StagePlanningStrategySystem(ExecuteProcessor):

    @override
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
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
            stage_entity.replace(PlanningAllowedComponent, stage_comp.name)

    ############################################################################################################
