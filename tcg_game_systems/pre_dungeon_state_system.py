from entitas import ExecuteProcessor, Matcher  # type: ignore
from typing import final, override
from game.tcg_game import TCGGame
from components.components import EnterStageFlagComponent, ActorComponent
from components.actions2 import (
    StatusUpdateAction,
    DEFAULT_NULL_ACTION,
    CandidateAction2,
)


@final
class PreDungeonStateSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###################################################################################################################################################################
    @override
    def execute(self) -> None:

        self._game._round_number = self._game._round_number + 1

        entities = self._game.get_group(
            Matcher(
                all_of=[
                    EnterStageFlagComponent,
                ],
            )
        ).entities

        # 这个pass，添加动作。
        for entity1 in entities:
            # 添加这个动作。
            assert not entity1.has(StatusUpdateAction)
            entity1.replace(StatusUpdateAction, DEFAULT_NULL_ACTION)

        entities2 = self._game.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                ],
            )
        ).entities

        for actor_entity in entities2:
            self._game.append_human_message(
                actor_entity, f"# 提示！战斗回合开始 = {self._game._round_number}"
            )

            actor_entity.replace(CandidateAction2, actor_entity._name)

    ###################################################################################################################################################################
