from entitas import InitializeProcessor, ExecuteProcessor, Matcher, Entity  # type: ignore
from overrides import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from gameplay_systems.components import (
    AutoPlanningComponent,
    StageComponent,
    ActorComponent,
    EnterStageComponent,
)
from rpg_game.rpg_game import RPGGame
from typing import List, Dict, Optional, cast


class StagePlanningStrategySystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        stage_entities = self._context.get_group(Matcher(StageComponent)).entities
        for stage_entity in stage_entities:
            stage_comp = stage_entity.get(StageComponent)
            actors_in_stage = self._context._get_actors_in_stage(stage_comp.name)
            if len(actors_in_stage) == 0:
                continue
            if not stage_entity.has(AutoPlanningComponent):
                stage_entity.add(AutoPlanningComponent, stage_comp.name)

    ############################################################################################################
