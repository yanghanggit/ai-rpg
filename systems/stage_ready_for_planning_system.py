from auxiliary.cn_builtin_prompt import stage_plan_prompt
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (StageComponent, ActorComponent,
                                AutoPlanningComponent)
from loguru import logger
from auxiliary.base_data import PropData
from typing import List, Set

####################################################################################################################################
class StageReadyForPlanningSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
        
    def execute(self) -> None:
        # todo: ChaosSystem接入
        entities = self.context.get_group(Matcher(all_of=[StageComponent, AutoPlanningComponent])).entities
        for entity in entities:
            self.handle(entity)
####################################################################################################################################
    def handle(self, entity: Entity) -> None:
        stage_comp: StageComponent = entity.get(StageComponent)
        #logger.info(f"StageReadyForPlanningSystem: {stage_comp.name} is ready for planning.")
        props_in_stage: List[PropData] = self.get_props_in_stage(entity)

        npcs_in_stage = self.context.actors_in_stage(stage_comp.name)
        npcnames: Set[str] = set()
        for npc in npcs_in_stage:
            npccomp: ActorComponent = npc.get(ActorComponent)
            npcnames.add(npccomp.name)
            #npcnames.add(npc.name)


        prompt = stage_plan_prompt(props_in_stage, npcnames, self.context)
        self.context.agent_connect_system.add_async_request_task(stage_comp.name, prompt)
####################################################################################################################################
    def get_props_in_stage(self, entity: Entity) -> List[PropData]:
        res: List[PropData] = []
        filesystem = self.context.file_system
        safe_stage_name = self.context.safe_get_entity_name(entity)
        files = filesystem.get_prop_files(safe_stage_name)
        for file in files:
            res.append(file.prop)
        return res
####################################################################################################################################