from entitas import ExecuteProcessor, Matcher, Entity, Matcher  # type: ignore
from typing import final, override
from game.tcg_game import TCGGame
from components.components_v_0_0_1 import (
    HandComponent,
)


@final
class PostDungeonStateSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:
        self._remove_hand_components()

    ############################################################################################################
    def _remove_hand_components(self) -> None:
        actor_entities = self._game.get_group(Matcher(HandComponent)).entities.copy()
        for entity in actor_entities:
            entity.remove(HandComponent)

    ############################################################################################################
