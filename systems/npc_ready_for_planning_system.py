from auxiliary.cn_builtin_prompt import npc_plan_prompt, first_time_npc_plan_prompt
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (NPCComponent,
                                AutoPlanningComponent)
from loguru import logger


            #     self.batch_message_remember_begin(npcentity, npcname, str_init_memory)
            #     self.batch_message_check_status(npcentity, npcname, str_props_info)
            #     self.batch_message_stages(npcentity, npcname, cast(str, npccomp.current_stage), str_where_you_can_go)
            #     self.batch_message_npc_archive(npcentity, npcname, str_who_you_know)
            #     self.batch_message_npc_appearance_in_stage(npcentity, npcname, appearance_data) 
            #     self.batch_message_remember_end(npcentity, npcname)


class NPCReadyForPlanningSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
        
    def execute(self) -> None:
        # todo: ChaosSystem接入
        entities = self.context.get_group(Matcher(all_of=[NPCComponent, AutoPlanningComponent])).entities
        for entity in entities:
            self.handle(entity)

    def handle(self, entity: Entity) -> None:
        npc_comp: NPCComponent = entity.get(NPCComponent)
        logger.info(f"NPCReadyForPlanningSystem: {npc_comp.name} is ready for planning.")

        prompt = npc_plan_prompt(entity, self.context)
        if self.context.execute_count == 1:
            prompt = first_time_npc_plan_prompt(entity, self.context)
        else:
            prompt = npc_plan_prompt(entity, self.context)

        #prompt = npc_plan_prompt(entity, self.context)
        self.context.agent_connect_system.add_async_requet_task(npc_comp.name, prompt)