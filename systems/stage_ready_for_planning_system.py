from auxiliary.cn_builtin_prompt import stage_plan_prompt
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (StageComponent, ActorComponent, AutoPlanningComponent)
from loguru import logger
from auxiliary.base_data import PropData
from typing import List, Set, override

####################################################################################################################################
class StageReadyForPlanningSystem(ExecuteProcessor):

    """
    所有stage 准备做计划。用于并行request的准备。
    """
        
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
####################################################################################################################################
    @override
    def execute(self) -> None:
        # todo: ChaosSystem接入
        entities = self.context.get_group(Matcher(all_of=[StageComponent, AutoPlanningComponent])).entities
        for entity in entities:
            self.handle(entity)
####################################################################################################################################
    def handle(self, entity: Entity) -> None:
        stage_comp: StageComponent = entity.get(StageComponent)
        props_in_stage: List[PropData] = self.get_props_in_stage(entity)
        actor_names_in_stage: Set[str] = self.get_actor_names_in_stage(entity)
        prompt = stage_plan_prompt(props_in_stage, actor_names_in_stage, self.context)
        self.context.agent_connect_system.add_async_request_task(stage_comp.name, prompt)
####################################################################################################################################
    # 获取场景内所有的actor的名字，用于场景计划。似乎不需要外观的信息？
    def get_actor_names_in_stage(self, entity: Entity) -> Set[str]:
        stage_comp: StageComponent = entity.get(StageComponent)
        _actors_in_stage = self.context.actors_in_stage(stage_comp.name)
        _names: Set[str] = set()
        for _en in _actors_in_stage:
            actor_comp: ActorComponent = _en.get(ActorComponent)
            _names.add(actor_comp.name)
        return _names
####################################################################################################################################
    # 获取场景内所有的道具的描述。
    def get_props_in_stage(self, entity: Entity) -> List[PropData]:
        res: List[PropData] = []
        filesystem = self.context.file_system
        safe_stage_name = self.context.safe_get_entity_name(entity)
        files = filesystem.get_prop_files(safe_stage_name)
        for file in files:
            res.append(file.prop)
        return res
####################################################################################################################################