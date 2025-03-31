from loguru import logger
from entitas import ExecuteProcessor, Matcher  # type: ignore
from typing import final, override
from game.tcg_game import TCGGame
from components.components_v_0_0_1 import (
    StagePermitComponent,
    ActorPermitComponent,
)


@final
class HomePostPlanningSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:
        self._remove_all_permits()

    ############################################################################################################
    def _remove_all_permits(self) -> None:
        actor_entities = self._game.get_group(
            Matcher(
                all_of=[
                    ActorPermitComponent,
                ],
            )
        ).entities.copy()
        for entity in actor_entities:
            logger.debug(
                f"PostPlanningSystem: 清理动作: ActorPermitComponent from entity: {entity._name}"
            )
            entity.remove(ActorPermitComponent)

        stage_entities = self._game.get_group(
            Matcher(
                all_of=[
                    StagePermitComponent,
                ]
            )
        ).entities.copy()
        for entity in stage_entities:
            logger.debug(
                f"PostPlanningSystem: 清理动作: StagePermitComponent from entity: {entity._name}"
            )
            entity.remove(StagePermitComponent)

    ############################################################################################################
