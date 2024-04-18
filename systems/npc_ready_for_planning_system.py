from auxiliary.prompt_maker import npc_plan_prompt
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (NPCComponent,
                                AutoPlanningComponent)
from loguru import logger


class NPCReadyForPlanningSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
        
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  StageReadyForPlanningSystem  >>>>>>>>>>>>>>>>>")
        # todo: ChaosSystem接入
        entities = self.context.get_group(Matcher(all_of=[NPCComponent, AutoPlanningComponent])).entities
        for entity in entities:
            self.handle(entity)

    def handle(self, entity: Entity) -> None:
        npc_comp: NPCComponent = entity.get(NPCComponent)
        logger.info(f"NPCReadyForPlanningSystem: {npc_comp.name} is ready for planning.")
        prompt = npc_plan_prompt(entity, self.context)
        self.context.agent_connect_system.add_async_requet_task(npc_comp.name, prompt)