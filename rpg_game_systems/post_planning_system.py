from entitas import ExecuteProcessor  # type: ignore
from game.rpg_game_context import RPGGameContext
from typing import final, override
from game.rpg_game import RPGGame


@final
class PostPlanningSystem(ExecuteProcessor):
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        # 啥也不做
        pass
