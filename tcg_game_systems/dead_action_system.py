from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import final, override, cast
from components.components import (
    DestroyFlagComponent,
)
from components.actions import (
    DeadAction,
)
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame


@final
class DeadActionSystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    ########################################################################################################################################################################
    @override
    def execute(self) -> None:
        # 添加销毁
        self._add_destory()

    ########################################################################################################################################################################
    def _add_destory(self) -> None:
        entities = self._context.get_group(Matcher(DeadAction)).entities
        for entity in entities:
            dead_caction = entity.get(DeadAction)
            entity.replace(DestroyFlagComponent, dead_caction.name)


########################################################################################################################################################################
