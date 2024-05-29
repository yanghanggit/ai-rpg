from overrides import override
from auxiliary.cn_builtin_prompt import npc_plan_prompt
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (NPCComponent,
                                AutoPlanningComponent,
                                EnviroNarrateActionComponent)
from loguru import logger
from auxiliary.actor_action import ActorAction



class NPCReadyForPlanningSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
####################################################################################################################################
    @override       
    def execute(self) -> None:
        # todo: ChaosSystem接入
        entities = self.context.get_group(Matcher(all_of=[NPCComponent, AutoPlanningComponent])).entities
        for entity in entities:
            self.handle(entity)
####################################################################################################################################
    def handle(self, entity: Entity) -> None:
        
        npccomp: NPCComponent = entity.get(NPCComponent)
        #logger.info(f"NPCReadyForPlanningSystem: {npccomp.name} is ready for planning.")
                
        tp = self.get_stage_enviro_narrate(entity)
        stagename = tp[0]
        #assert stagename != ""
        stage_enviro_narrate = tp[1]
        #assert stage_enviro_narrate != ""
        
        prompt = npc_plan_prompt(stagename, stage_enviro_narrate, self.context)
        self.context.agent_connect_system.add_async_requet_task(npccomp.name, prompt)
####################################################################################################################################
    def get_stage_enviro_narrate(self, entity: Entity) -> tuple[str, str]:

        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None:
            logger.error("stage is None, npc无所在场景是有问题的")
            return "", ""
        
        stagename = self.context.safe_get_entity_name(stageentity)
        stage_enviro_narrate = ""
        if stageentity.has(EnviroNarrateActionComponent):
            envirocomp: EnviroNarrateActionComponent = stageentity.get(EnviroNarrateActionComponent)
            action: ActorAction = envirocomp.action
            if len(action.values) > 0:
                stage_enviro_narrate = action.single_value()

        return stagename, stage_enviro_narrate
####################################################################################################################################