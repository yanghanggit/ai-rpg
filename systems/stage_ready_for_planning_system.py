from auxiliary.prompt_maker import stage_plan_prompt
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (StageComponent,
                                AutoPlanningComponent)
from loguru import logger


class StageReadyForPlanningSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
        
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  StageReadyForPlanningSystem  >>>>>>>>>>>>>>>>>")
        # todo: ChaosSystem接入
        entities = self.context.get_group(Matcher(all_of=[StageComponent, AutoPlanningComponent])).entities
        for entity in entities:
            self.handle(entity)

    def handle(self, entity: Entity) -> None:
        stage_comp: StageComponent = entity.get(StageComponent)
        logger.info(f"StageReadyForPlanningSystem: {stage_comp.name} is ready for planning.")
        prompt = stage_plan_prompt(entity, self.context)
        self.context.agent_connect_system.add_async_requet_task(stage_comp.name, prompt)