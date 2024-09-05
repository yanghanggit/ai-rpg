from entitas import ExecuteProcessor  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override
from rpg_game.rpg_game import RPGGame


class PostPlanningSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        # 啥也不做
        pass

############################################################################################################
