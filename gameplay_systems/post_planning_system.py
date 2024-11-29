from entitas import ExecuteProcessor  # type: ignore
from game.rpg_entitas_context import RPGEntitasContext
from typing import final, override
from game.rpg_game import RPGGame


@final
class PostPlanningSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        # 啥也不做
        pass
