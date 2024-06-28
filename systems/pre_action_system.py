from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from systems.components import AutoPlanningComponent
from typing import Set, override
   
class PreActionSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    @override
    def execute(self) -> None:
        pass
        ## 自我测试，这个阶段不允许有任何的planning
        #planningentities: Set[Entity] = self.context.get_group(Matcher(AutoPlanningComponent)).entities
        # assert len(planningentities) == 0, "AutoPlanningComponent should be removed in PostPlanningSystem"
############################################################################################################
   

