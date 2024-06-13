from overrides import override
from auxiliary.cn_builtin_prompt import actpr_plan_prompt
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (ActorComponent, AutoPlanningComponent, EnviroNarrateActionComponent)
from loguru import logger
from auxiliary.actor_plan_and_action import ActorAction


class ActorReadyForPlanningSystem(ExecuteProcessor):

    """
    所有actor 准备做计划。用于并行request的准备。
    """

    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
####################################################################################################################################
    @override       
    def execute(self) -> None:
        # todo: ChaosSystem接入
        entities = self.context.get_group(Matcher(all_of=[ActorComponent, AutoPlanningComponent])).entities
        for entity in entities:
            self.handle(entity)
####################################################################################################################################
    def handle(self, entity: Entity) -> None:        
        actor_comp: ActorComponent = entity.get(ActorComponent)
        tp = self.get_stage_enviro_narrate(entity)
        stage_name = tp[0]
        stage_enviro_narrate = tp[1]
        if stage_name == "" or stage_enviro_narrate == "":
            logger.error("stagename or stage_enviro_narrate is None") # 放弃这个actor的计划
            return
        
        # 必须要有一个stage的环境描述，否则无法做计划。
        prompt = actpr_plan_prompt(stage_name, stage_enviro_narrate, self.context)
        self.context.agent_connect_system.add_async_request_task(actor_comp.name, prompt)
####################################################################################################################################
    # 获取场景的环境描述
    def get_stage_enviro_narrate(self, entity: Entity) -> tuple[str, str]:

        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
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