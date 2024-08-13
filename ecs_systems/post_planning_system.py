
from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from ecs_systems.components import AutoPlanningComponent
from typing import Set, override

class PostPlanningSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext) -> None:
        self._context: RPGEntitasContext = context
############################################################################################################
    @override
    def execute(self) -> None:
        entities = self._context.get_group(Matcher(AutoPlanningComponent)).entities.copy()
        for entity in entities:
            entity.remove(AutoPlanningComponent)
############################################################################################################

