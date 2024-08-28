from entitas import ExecuteProcessor  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override
from rpg_game.rpg_game import RPGGame


class PreActionSystem(ExecuteProcessor):
    ############################################################################################################
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        self.test()

    ############################################################################################################
    def test(self) -> None:
        pass
        ## 自我测试，这个阶段不允许有任何的planning
        # planningentities: Set[Entity] = self.context.get_group(Matcher(AutoPlanningComponent)).entities
        # assert len(planningentities) == 0, "AutoPlanningComponent should be removed in PostPlanningSystem"

    ############################################################################################################
