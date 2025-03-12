from entitas import ExecuteProcessor, Matcher  # type: ignore
from typing import final, override
from game.tcg_game import TCGGame
from components.components import (
    StageNarratePlanningPermitFlagComponent,
    ActorRolePlayPlanningPermitFlagComponent,
)


@final
class PostPlanningSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:
        # 删掉所有permitflag
        self._remove_all_planning_permit()

    ############################################################################################################
    def _remove_all_planning_permit(self) -> None:
        # 后续可以考虑给所有planning , TODO
        actor_entities = self._game.get_group(
            Matcher(
                all_of=[
                    ActorRolePlayPlanningPermitFlagComponent,
                ],
            )
        ).entities.copy()
        for entity in actor_entities:
            entity.remove(ActorRolePlayPlanningPermitFlagComponent)

        stage_entities = self._game.get_group(
            Matcher(
                all_of=[
                    StageNarratePlanningPermitFlagComponent,
                ]
            )
        ).entities.copy()
        for entity in stage_entities:
            entity.remove(StageNarratePlanningPermitFlagComponent)
