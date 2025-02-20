from entitas import ExecuteProcessor, Matcher  # type: ignore
from typing import final, override, cast
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from components.components import (
    StageNarratePlanningPermitFlagComponent,
    ActorRolePlayPlanningPermitFlagComponent,
)


@final
class PostPlanningSystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    ############################################################################################################
    @override
    def execute(self) -> None:
        # 删掉所有permitflag
        self._remove_all_planning_permit()

    ############################################################################################################
    def _remove_all_planning_permit(self) -> None:
        # 后续可以考虑给所有planning , TODO
        actor_entities = self._context.get_group(
            Matcher(
                all_of=[
                    ActorRolePlayPlanningPermitFlagComponent,
                ],
            )
        ).entities.copy()
        for entity in actor_entities:
            entity.remove(ActorRolePlayPlanningPermitFlagComponent)

        stage_entities = self._context.get_group(
            Matcher(
                all_of=[
                    StageNarratePlanningPermitFlagComponent,
                ]
            )
        ).entities.copy()
        for entity in stage_entities:
            entity.remove(StageNarratePlanningPermitFlagComponent)
