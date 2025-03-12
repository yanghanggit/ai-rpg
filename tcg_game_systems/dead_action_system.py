from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import final, override
from components.components import (
    DestroyFlagComponent,
)
from components.actions import (
    DeadAction,
)
from game.tcg_game import TCGGame


@final
class DeadActionSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ########################################################################################################################################################################
    @override
    def execute(self) -> None:
        # 添加销毁
        self._add_destory()

    ########################################################################################################################################################################
    def _add_destory(self) -> None:
        entities = self._game.get_group(Matcher(DeadAction)).entities
        for entity in entities:
            dead_caction = entity.get(DeadAction)
            entity.replace(DestroyFlagComponent, dead_caction.name)


########################################################################################################################################################################
