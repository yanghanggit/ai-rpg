
from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from ecs_systems.components import AutoPlanningComponent
from typing import Set, override

class PostPlanningSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self._context: ExtendedContext = context
############################################################################################################
    @override
    def execute(self) -> None:
        entities: Set[Entity] = self._context.get_group(Matcher(AutoPlanningComponent)).entities.copy()
        for entity in entities.copy():
            entity.remove(AutoPlanningComponent)
############################################################################################################

