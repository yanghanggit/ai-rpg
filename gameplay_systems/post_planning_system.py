from entitas import ExecuteProcessor, Matcher  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from gameplay_systems.components import AutoPlanningComponent
from typing import override
from rpg_game.rpg_game import RPGGame


class PostPlanningSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        entities = self._context.get_group(
            Matcher(AutoPlanningComponent)
        ).entities.copy()
        for entity in entities:
            entity.remove(AutoPlanningComponent)


############################################################################################################
