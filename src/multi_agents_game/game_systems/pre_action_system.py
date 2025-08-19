from typing import final, override

from ..entitas import ExecuteProcessor
from ..game.tcg_game import TCGGame


@final
class PreActionSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    @override
    async def execute(self) -> None:
        pass
