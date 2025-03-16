from entitas import ExecuteProcessor, Matcher  # type: ignore
from typing import final, override
from game.tcg_game import TCGGame
from components.components import ActorComponent
from components.actions2 import (
    CandidateAction2,
)


@final
class DungeonStateActorPlanningSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###################################################################################################################################################################
    @override
    def execute(self) -> None:

        self._game._round_number = self._game._round_number + 1

        entities2 = self._game.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                ],
            )
        ).entities

        for actor_entity in entities2:

            stage_entity = self._game.safe_get_stage_entity(actor_entity)
            assert stage_entity is not None

            self._game.append_human_message(
                entity=actor_entity,
                chat=f"# 提示！战斗回合开始 = {self._game._round_number}",
                tag=f"battle:{stage_entity._name}:{self._game._round_number}",
            )

            actor_entity.replace(CandidateAction2, actor_entity._name)

    ###################################################################################################################################################################
