from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from ecs_systems.components import AutoPlanningComponent
from typing import Set, override
   
class PreActionSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: RPGEntitasContext) -> None:
        self._context: RPGEntitasContext = context
############################################################################################################
    @override
    def execute(self) -> None:
        pass
        ## 自我测试，这个阶段不允许有任何的planning
        #planningentities: Set[Entity] = self.context.get_group(Matcher(AutoPlanningComponent)).entities
        # assert len(planningentities) == 0, "AutoPlanningComponent should be removed in PostPlanningSystem"
############################################################################################################
   

